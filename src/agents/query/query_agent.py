"""QueryAgent: NL question -> LLM Cypher -> safe Neo4j read."""

from __future__ import annotations

import json
import logging
import re
from typing import Any, Protocol

from config import Settings
from logging_context import new_run_id

from agents.extraction.llm_client import LLMClient
from agents.query.cypher_guard import verify_read_only_cypher
from agents.query.models import QueryRequest, QueryResponse


class GraphQueryStore(Protocol):
    def run_read(self, query: str, params: dict[str, Any] | None = None) -> list[dict[str, Any]]: ...


class QueryAgent:
    def __init__(self, *, settings: Settings, graph_store: GraphQueryStore) -> None:
        self._settings = settings
        self._graph_store = graph_store
        self._log = logging.getLogger("query.agent")
        self._client = LLMClient(
            base_url=settings.query_llm_base_url,
            api_key=settings.query_llm_api_key,
            timeout_seconds=settings.query_llm_timeout_seconds,
            max_retries=0,
        )

    def answer(self, req: QueryRequest) -> QueryResponse:
        query_id = new_run_id()
        warnings: list[str] = []
        draft = self._repair_generated_cypher(self._generate_cypher(req.question))
        ok, cypher, err = verify_read_only_cypher(draft, max_limit=self._settings.query_max_limit)
        if not ok:
            return QueryResponse(
                answer="I could not build a safe read-only graph query for that question.",
                evidence=[],
                cypher=draft if req.include_cypher else None,
                query_id=query_id,
                warnings=[err or "query rejected"],
            )

        try:
            rows = self._graph_store.run_read(cypher, None)
        except Exception as exc:
            self._log.warning("query_execution_failed query_id=%s error=%s", query_id, str(exc))
            fallback = self._retry_with_deterministic_cypher(
                question=req.question,
                original_cypher=cypher,
                query_id=query_id,
                original_error=exc,
                warnings=warnings,
            )
            if fallback is not None:
                cypher, rows = fallback
            else:
                return QueryResponse(
                    answer="I could not execute the generated graph query safely.",
                    evidence=[],
                    cypher=cypher if req.include_cypher else None,
                    query_id=query_id,
                    warnings=[f"query_execution_failed:{type(exc).__name__}"],
                )
        evidence = [self._to_json_safe(x) for x in rows[: self._settings.query_max_evidence_rows]]
        answer = self._synthesize_answer(req.question, evidence, warnings)
        return QueryResponse(
            answer=answer,
            evidence=evidence,
            cypher=cypher if req.include_cypher else None,
            query_id=query_id,
            warnings=warnings,
        )

    @staticmethod
    def _repair_generated_cypher(cypher: str) -> str:
        """Normalize common model output quirks into Neo4j-compatible syntax."""
        q = cypher.strip()
        # Neo4j rejects COUNT((pattern)); convert it to COUNT { pattern }.
        q = re.sub(
            r"\bCOUNT\(\(\s*(.*?)\s*\)\)",
            lambda m: f"COUNT {{ ({m.group(1).strip()}) }}",
            q,
            flags=re.IGNORECASE,
        )
        # Neo4j expects COUNT { pattern }, not COUNT({pattern})
        q = re.sub(r"\bCOUNT\(\s*\{", "COUNT {", q, flags=re.IGNORECASE)
        q = re.sub(r"\}\s*\)", " }", q)
        q = re.sub(r"\bCOUNT\s*\{\s*\(", "COUNT { (", q, flags=re.IGNORECASE)
        q = re.sub(r"\)\s*\}", ") }", q)
        return q

    def _retry_with_deterministic_cypher(
        self,
        *,
        question: str,
        original_cypher: str,
        query_id: str,
        original_error: Exception,
        warnings: list[str],
    ) -> tuple[str, list[dict[str, Any]]] | None:
        fallback_draft = self._repair_generated_cypher(self._generate_cypher_deterministic(question))
        if fallback_draft.strip() == (original_cypher or "").strip():
            return None
        ok, fallback_cypher, err = verify_read_only_cypher(
            fallback_draft,
            max_limit=self._settings.query_max_limit,
        )
        if not ok:
            warnings.append(f"query_execution_failed:{type(original_error).__name__}")
            warnings.append(f"deterministic_fallback_rejected:{err or 'query rejected'}")
            return None
        try:
            rows = self._graph_store.run_read(fallback_cypher, None)
        except Exception as fallback_exc:
            warnings.append(f"query_execution_failed:{type(original_error).__name__}")
            warnings.append(f"deterministic_fallback_failed:{type(fallback_exc).__name__}")
            self._log.warning(
                "query_execution_fallback_failed query_id=%s original_error=%s fallback_error=%s",
                query_id,
                str(original_error),
                str(fallback_exc),
            )
            return None
        warnings.append(f"query_execution_failed:{type(original_error).__name__}")
        warnings.append("deterministic_fallback_used")
        self._log.info(
            "query_execution_fallback_succeeded query_id=%s fallback_cypher=%s",
            query_id,
            fallback_cypher,
        )
        return fallback_cypher, rows

    def _generate_cypher(self, question: str) -> str:
        # Offline / load-test mode uses a tiny deterministic translator so the
        # project still answers the core demo query without live model access.
        if not self._settings.query_llm_enabled:
            return self._generate_cypher_deterministic(question)
        if not self._settings.query_llm_api_key:
            return "MATCH (n) RETURN n.node_id AS node_id LIMIT 10"
        return self._generate_cypher_llm(question)

    def _generate_cypher_deterministic(self, question: str) -> str:
        text = re.sub(r"[^a-z0-9]+", " ", question.lower()).strip()
        limit = min(self._settings.query_max_limit, 10)

        coappearance_terms = (
            "appeared together",
            "appear together",
            "co occurrence",
            "cooccur",
            "co occur",
        )
        if any(term in text for term in coappearance_terms):
            return (
                "MATCH (a:CanonicalEntity)-[ra]->(p:Post)<-[rb]-(b:CanonicalEntity) "
                "WHERE type(ra) IN ['MENTIONS', 'TAGGED_IN'] "
                "AND type(rb) IN ['MENTIONS', 'TAGGED_IN'] "
                "AND a.node_id < b.node_id "
                "RETURN "
                "coalesce(a.canonical_surface, a.node_id) AS entity_a, "
                "coalesce(b.canonical_surface, b.node_id) AS entity_b, "
                "count(DISTINCT p) AS shared_posts, "
                "collect(DISTINCT p.platform_post_id)[0..5] AS post_ids "
                f"ORDER BY shared_posts DESC, entity_a ASC, entity_b ASC LIMIT {limit}"
            )

        if "hashtag" in text or "topic" in text or "tag" in text:
            return (
                "MATCH (t:CanonicalEntity)-[:TAGGED_IN]->(p:Post) "
                "RETURN "
                "coalesce(t.canonical_surface, t.node_id) AS topic, "
                "count(DISTINCT p) AS post_count "
                f"ORDER BY post_count DESC, topic ASC LIMIT {limit}"
            )

        if "mention" in text:
            return (
                "MATCH (e:CanonicalEntity)-[:MENTIONS]->(p:Post) "
                "RETURN "
                "coalesce(e.canonical_surface, e.node_id) AS entity, "
                "count(DISTINCT p) AS mention_count "
                f"ORDER BY mention_count DESC, entity ASC LIMIT {limit}"
            )

        return f"MATCH (n) RETURN n.node_id AS node_id LIMIT {limit}"

    def _generate_cypher_llm(self, question: str) -> str:
        schema = self._schema_summary()
        prompt = (
            "Task: Translate the question into ONE read-only Cypher query for Neo4j.\n"
            "Hard rules:\n"
            "- Output ONLY JSON: {\"cypher\":\"...\"}\n"
            "- No prose, no markdown, no code fences, no <think> content\n"
            "- Cypher must be read-only (MATCH/OPTIONAL MATCH/WITH/RETURN)\n"
            "- No mutation clauses (CREATE/MERGE/SET/DELETE/CALL)\n"
            "- Do NOT use size((pattern)); use COUNT { pattern } instead\n"
            "- Include LIMIT <= "
            f"{self._settings.query_max_limit}.\n"
            "Use only labels, relationship types, and properties present in the schema summary.\n"
            f"Schema summary: {schema}\n"
            f"Question: {question}\n"
        )
        resp = self._client.generate_json(
            model=self._settings.query_llm_model,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a Cypher translator. Return strict JSON only with key 'cypher'. "
                        "Never include analysis, chain-of-thought, or <think>. /no_think"
                    ),
                },
                {"role": "user", "content": prompt},
            ],
            temperature=0.0,
            max_tokens=220,
        )
        d = self._to_dict(resp)
        self._log.info("query_llm_raw_cypher_response=%s", json.dumps(d, default=str))
        choices = d.get("choices") or []
        if not choices:
            return "MATCH (n) RETURN n.node_id AS node_id LIMIT 10"
        finish_reason = choices[0].get("finish_reason")
        if finish_reason == "length":
            self._log.warning("query_llm_cypher_truncated finish_reason=length; using guarded fallback path if needed")
        content = self._extract_message_content(choices[0].get("message", {}))
        text = self._clean_model_text(content)
        try:
            obj = self._parse_json_content(text)
            if isinstance(obj, dict) and isinstance(obj.get("cypher"), str):
                return obj["cypher"]
        except Exception:
            pass
        return "MATCH (n) RETURN n.node_id AS node_id LIMIT 10"

    def _schema_summary(self) -> str:
        try:
            labels = self._graph_store.run_read(
                "MATCH (n) RETURN DISTINCT labels(n) AS labels LIMIT 50",
                None,
            )
            rels = self._graph_store.run_read(
                "MATCH ()-[r]->() RETURN DISTINCT type(r) AS type LIMIT 50",
                None,
            )
            node_props = self._graph_store.run_read(
                "MATCH (n) "
                "UNWIND labels(n) AS label "
                "UNWIND keys(n) AS key "
                "RETURN label, collect(DISTINCT key)[0..30] AS properties "
                "ORDER BY label ASC LIMIT 50",
                None,
            )
            rel_props = self._graph_store.run_read(
                "MATCH ()-[r]->() "
                "UNWIND keys(r) AS key "
                "RETURN type(r) AS rel_type, collect(DISTINCT key)[0..30] AS properties "
                "ORDER BY rel_type ASC LIMIT 50",
                None,
            )
            rel_patterns = self._graph_store.run_read(
                "MATCH (a)-[r]->(b) "
                "RETURN head(labels(a)) AS from_label, type(r) AS rel_type, head(labels(b)) AS to_label, "
                "count(*) AS freq "
                "ORDER BY freq DESC LIMIT 50",
                None,
            )
            return json.dumps(
                {
                    "labels": [x.get("labels") for x in labels],
                    "rel_types": [x.get("type") for x in rels],
                    "node_properties_by_label": node_props,
                    "relationship_properties_by_type": rel_props,
                    "relationship_patterns": rel_patterns,
                },
                default=str,
            )
        except Exception:
            return '{"labels":[],"rel_types":[]}'

    def _synthesize_answer(self, question: str, evidence: list[dict[str, Any]], warnings: list[str]) -> str:
        if self._settings.query_llm_enabled and self._settings.query_llm_api_key:
            try:
                answer = self._synthesize_answer_llm(question, evidence)
                if evidence and "no evidence found in the graph for this question" in answer.lower():
                    raise ValueError("llm_answer_contradicted_non_empty_evidence")
                return answer
            except Exception as exc:
                warnings.append(f"llm_answer_synthesis_failed_fallback:{type(exc).__name__}")
        if not evidence:
            return "No evidence found in the graph for this question."
        top = evidence[0]
        return f"Found {len(evidence)} evidence row(s). Top row: {json.dumps(top, ensure_ascii=True)}"

    def _synthesize_answer_llm(self, question: str, evidence: list[dict[str, Any]]) -> str:
        payload = {"question": question, "evidence_rows": evidence}
        prompt = (
            "Write user-friendly answer grounded only in evidence_rows.\n"
            "Do not invent facts. If rows are empty, say: No evidence found in the graph for this question.\n"
            "If entity values are pronouns/ambiguous (I, me, my wife, my husband, myself), "
            "refer to them as unnamed entities.\n"
            "Output ONLY JSON: {\"answer\":\"...\"}\n"
            f"Input: {json.dumps(payload, ensure_ascii=True)}"
        )
        resp = self._client.generate_json(
            model=self._settings.query_llm_model,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are an evidence-grounded answer synthesizer. "
                        "Return strict JSON only with key 'answer'. No reasoning. /no_think"
                    ),
                },
                {"role": "user", "content": prompt},
            ],
            temperature=0.0,
            max_tokens=220,
        )
        d = self._to_dict(resp)
        self._log.info("query_llm_raw_answer_response=%s", json.dumps(d, default=str))
        choices = d.get("choices") or []
        if not choices:
            raise ValueError("no llm answer choices")
        content = self._extract_message_content(choices[0].get("message", {}))
        obj = self._parse_json_content(content)
        if isinstance(obj, dict) and isinstance(obj.get("answer"), str) and obj["answer"].strip():
            return obj["answer"].strip()
        raise ValueError("invalid llm answer payload")

    @staticmethod
    def _extract_message_content(message: dict[str, Any]) -> str:
        content = message.get("content")
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            out: list[str] = []
            for part in content:
                if isinstance(part, dict):
                    txt = part.get("text")
                    if isinstance(txt, str):
                        out.append(txt)
            return "\n".join(out)
        return ""

    @staticmethod
    def _clean_model_text(text: str) -> str:
        t = text.strip()
        t = re.sub(r"<think>.*?</think>", "", t, flags=re.DOTALL | re.IGNORECASE).strip()
        if t.startswith("```"):
            lines = t.splitlines()
            if len(lines) >= 3 and lines[0].startswith("```") and lines[-1].startswith("```"):
                t = "\n".join(lines[1:-1]).strip()
            if t.lower().startswith("json\n"):
                t = t.split("\n", 1)[1]
        return t

    @staticmethod
    def _parse_json_content(content: str) -> Any:
        text = QueryAgent._clean_model_text(content)
        try:
            return json.loads(text)
        except Exception:
            pass
        candidate = QueryAgent._extract_first_json_object(text)
        if candidate is not None:
            try:
                return json.loads(candidate)
            except Exception:
                pass
        salvaged = QueryAgent._salvage_truncated_json(text)
        if salvaged is not None:
            return salvaged
        raise ValueError("No parsable JSON content")

    @staticmethod
    def _extract_first_json_object(text: str) -> str | None:
        start = text.find("{")
        if start == -1:
            return None
        depth = 0
        in_string = False
        escaped = False
        for idx in range(start, len(text)):
            ch = text[idx]
            if in_string:
                if escaped:
                    escaped = False
                elif ch == "\\":
                    escaped = True
                elif ch == '"':
                    in_string = False
                continue
            if ch == '"':
                in_string = True
            elif ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    return text[start : idx + 1]
        return None

    @staticmethod
    def _salvage_truncated_json(text: str) -> Any:
        start = text.find("{")
        if start == -1:
            return None
        body = text[start:]
        depth_brace = 0
        depth_bracket = 0
        in_string = False
        escaped = False
        last_good = -1
        for idx, ch in enumerate(body):
            if in_string:
                if escaped:
                    escaped = False
                elif ch == "\\":
                    escaped = True
                elif ch == '"':
                    in_string = False
                continue
            if ch == '"':
                in_string = True
            elif ch == "{":
                depth_brace += 1
            elif ch == "}":
                depth_brace -= 1
                if depth_brace == 0 and depth_bracket == 0:
                    last_good = idx + 1
            elif ch == "[":
                depth_bracket += 1
            elif ch == "]":
                depth_bracket -= 1
        if last_good > 0:
            try:
                return json.loads(body[:last_good])
            except Exception:
                pass
        trimmed = body
        if in_string:
            trimmed += '"'
        trimmed = re.sub(r"[,\s]*$", "", trimmed)
        trimmed = re.sub(r',\s*"[^"]*"\s*:\s*[^,\]\}]*$', "", trimmed)
        trimmed = re.sub(r',\s*[^,\]\}]*$', "", trimmed)
        closers = "]" * max(0, depth_bracket) + "}" * max(0, depth_brace)
        for attempt in (trimmed + closers, trimmed.rstrip(",") + closers):
            try:
                return json.loads(attempt)
            except Exception:
                continue
        return None

    @staticmethod
    def _to_dict(response: Any) -> dict[str, Any]:
        if isinstance(response, dict):
            return response
        model_dump = getattr(response, "model_dump", None)
        if callable(model_dump):
            dumped = model_dump()
            if isinstance(dumped, dict):
                return dumped
        return {}

    @staticmethod
    def _to_json_safe(value: Any) -> Any:
        if value is None or isinstance(value, str | int | float | bool):
            return value
        if isinstance(value, dict):
            return {str(k): QueryAgent._to_json_safe(v) for k, v in value.items()}
        if isinstance(value, list | tuple | set):
            return [QueryAgent._to_json_safe(v) for v in value]
        # Neo4j Node/Relationship are mapping-like; dict(value) usually returns properties.
        try:
            mapped = dict(value)  # type: ignore[arg-type]
            return {str(k): QueryAgent._to_json_safe(v) for k, v in mapped.items()}
        except Exception:
            pass
        return str(value)
