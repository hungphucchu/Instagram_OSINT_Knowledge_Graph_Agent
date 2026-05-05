"""LLM extractor using OpenAI-compatible client SDK."""

from __future__ import annotations

import json
import logging
import re
from typing import Any

from agents.extraction.heuristic_extractor import HeuristicExtractor
from agents.extraction.llm_client import LLMClient
from schemas.extraction_record import ExtractedEntity, ExtractedRelation
from schemas.raw_artifact import RawArtifact

_MAX_CAPTION_CHARS = 1500
_MAX_OUTPUT_TOKENS = 1536


class LLMExtractor:
    """
    LLM-first extractor interface for future Instructor/OpenAI-compatible wiring.

    For now, this class intentionally falls back to deterministic heuristics so
    CI and local runs do not require network keys.
    """

    def __init__(
        self,
        *,
        provider: str,
        model_id: str,
        base_url: str,
        api_key: str,
        timeout_seconds: int,
        fallback: HeuristicExtractor,
    ) -> None:
        self._provider = provider
        self._model_id = model_id
        self._base_url = base_url.rstrip("/")
        self._api_key = api_key
        self._timeout_seconds = timeout_seconds
        self._fallback = fallback
        self._llm_disabled = False
        self._client = LLMClient(
            base_url=self._base_url,
            api_key=self._api_key,
            timeout_seconds=self._timeout_seconds,
            max_retries=0,
        )
        self._log = logging.getLogger("extraction.llm_extractor")

    def extract(self, artifact: RawArtifact) -> tuple[list[ExtractedEntity], list[ExtractedRelation]]:
        if not self._api_key or self._llm_disabled:
            if not self._api_key:
                self._log.info("llm_fallback reason=no_api_key artifact_id=%s", artifact.artifact_id)
            elif self._llm_disabled:
                self._log.info(
                    "llm_fallback reason=llm_disabled artifact_id=%s",
                    artifact.artifact_id,
                )
            return self._fallback.extract(artifact)

        try:
            payload = self._build_payload(artifact)
            response = self._client.generate_json(
                model=payload["model"],
                messages=payload["messages"],
                temperature=payload["temperature"],
                max_tokens=_MAX_OUTPUT_TOKENS,
            )
            entities, relations = self._parse_response_json(response)
            if not entities and not relations:
                self._log.info(
                    "llm_empty_output_fallback artifact_id=%s",
                    artifact.artifact_id,
                )
                return self._fallback.extract(artifact)
            return entities, relations
        except KeyboardInterrupt:
            raise
        except Exception as exc:
            name = type(exc).__name__
            if self._is_transport_error(exc):
                # Endpoint is dead/overloaded; trip circuit breaker so the remaining
                # artifacts in *this* extractor instance skip the LLM and fall back
                # to heuristics instead of paying N * timeout seconds.
                self._llm_disabled = True
                self._log.warning(
                    "llm_transport_error_disable artifact_id=%s provider=%s model=%s err=%s",
                    artifact.artifact_id,
                    self._provider,
                    self._model_id,
                    name,
                )
            else:
                # Parse/validation error on this specific artifact. Keep LLM enabled
                # for the next artifact because other artifacts may parse cleanly.
                self._log.warning(
                    "llm_parse_error_fallback artifact_id=%s provider=%s model=%s err=%s",
                    artifact.artifact_id,
                    self._provider,
                    self._model_id,
                    name,
                )
            return self._fallback.extract(artifact)

    @property
    def model_id(self) -> str:
        return f"{self._provider}:{self._model_id}"

    def _build_payload(self, artifact: RawArtifact) -> dict[str, Any]:
        caption = self._truncate(artifact.caption_text or "", _MAX_CAPTION_CHARS)
        prompt = (
            "Extract complex relationship tuples from the Instagram-style caption.\n"
            "Return STRICT JSON ONLY with keys: entities, relations. No prose, no markdown.\n"
            "Entity item keys: entity_type, surface_form, snippet, start_offset, end_offset, confidence.\n"
            "Relation item keys: subject, predicate, object, evidence_span, confidence.\n"
            "Rules:\n"
            "- Only infer relations grounded by explicit caption text.\n"
            "- Prefer specific predicates (MENTIONS, COLLABORATES_WITH, LOCATED_IN, WORKS_AT, TAGGED_IN).\n"
            "- If uncertain, keep confidence low instead of inventing facts.\n"
            "- Max 10 entities and 10 relations.\n\n"
            f"caption: {caption}\n"
            f"mentions: {artifact.mentions}\n"
            f"hashtags: {artifact.hashtags}\n"
            f"platform_post_id: {artifact.platform_post_id}\n"
        )
        # `/no_think` hint tells Qwen3-style reasoning models to skip <think>...</think>
        # which otherwise burns tokens and time on every call.
        system = (
            "You are a precise information extractor. "
            "Output valid JSON only, no explanations, no <think> blocks. /no_think"
        )
        return {
            "model": self._model_id,
            "temperature": 0.0,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": prompt},
            ],
        }

    @staticmethod
    def _truncate(text: str, limit: int) -> str:
        if len(text) <= limit:
            return text
        return text[:limit] + "…"

    @staticmethod
    def _is_transport_error(exc: BaseException) -> bool:
        name = type(exc).__name__.lower()
        module = getattr(type(exc), "__module__", "") or ""
        if "timeout" in name:
            return True
        if "connect" in name:
            return True
        if module.startswith("openai") and ("api" in name or "connection" in name):
            return True
        if module.startswith("httpx") or module.startswith("httpcore"):
            return True
        return isinstance(exc, (OSError, ConnectionError))

    def _parse_response_json(
        self, response: Any
    ) -> tuple[list[ExtractedEntity], list[ExtractedRelation]]:
        response_dict = self._response_to_dict(response)
        choices = response_dict.get("choices")
        if not isinstance(choices, list) or not choices:
            return [], []
        message = choices[0].get("message", {})
        content = self._extract_message_content(message)
        if not content.strip():
            return [], []
        parsed = self._parse_json_content(content)
        if not isinstance(parsed, dict):
            return [], []
        entities_raw = parsed.get("entities", [])
        relations_raw = parsed.get("relations", [])
        entities = self._coerce_entities(entities_raw)
        relations = self._coerce_relations(relations_raw)
        return entities, relations

    @staticmethod
    def _extract_message_content(message: dict[str, Any]) -> str:
        content = message.get("content")
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            text_parts: list[str] = []
            for part in content:
                if isinstance(part, dict):
                    text = part.get("text")
                    if isinstance(text, str):
                        text_parts.append(text)
            return "\n".join(text_parts)
        return ""

    @staticmethod
    def _parse_json_content(content: str) -> Any:
        text = content.strip()
        text = LLMExtractor._strip_reasoning_tags(text)
        if text.startswith("```"):
            lines = text.splitlines()
            # Drop first and last fence lines when present.
            if len(lines) >= 3 and lines[0].startswith("```") and lines[-1].startswith("```"):
                text = "\n".join(lines[1:-1]).strip()
            # Handle optional language marker like "json" on first line.
            if text.lower().startswith("json\n"):
                text = text.split("\n", 1)[1]
        # First try direct parse.
        try:
            return json.loads(text)
        except Exception:
            pass
        # Then try extracting first JSON object from mixed prose output.
        candidate = LLMExtractor._extract_first_json_object(text)
        if candidate is not None:
            try:
                return json.loads(candidate)
            except Exception:
                pass
        # Last resort: the response was truncated (hit max_tokens mid-object).
        # Try to repair by closing unbalanced braces/brackets starting at the
        # first "{" and return whatever parses. Salvages partial entities/relations.
        salvaged = LLMExtractor._salvage_truncated_json(text)
        if salvaged is not None:
            return salvaged
        raise ValueError("No parsable JSON object found in model output")

    @staticmethod
    def _strip_reasoning_tags(text: str) -> str:
        # Remove <think>...</think> style blocks emitted by some models.
        text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL | re.IGNORECASE).strip()
        # Handle the case where reasoning was truncated by max_tokens (unclosed <think>).
        open_tag = re.search(r"<think>", text, flags=re.IGNORECASE)
        close_tag = re.search(r"</think>", text, flags=re.IGNORECASE)
        if open_tag and not close_tag:
            text = text[: open_tag.start()].strip()
        return text

    @staticmethod
    def _salvage_truncated_json(text: str) -> Any:
        start = text.find("{")
        if start == -1:
            return None
        body = text[start:]
        # Strip anything after the last plausible closing bracket to improve odds.
        # Then repeatedly try to auto-close unbalanced {, [ brackets.
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
        # If we saw a full top-level object, parse that slice.
        if last_good > 0:
            try:
                return json.loads(body[:last_good])
            except Exception:
                pass
        # Otherwise try to repair by trimming trailing comma / partial key/value
        # and appending missing closers.
        trimmed = body
        if in_string:
            trimmed += '"'
        trimmed = re.sub(r"[,\s]*$", "", trimmed)
        # Drop dangling "key":  or partial token at end.
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
    def _response_to_dict(response: Any) -> dict[str, Any]:
        if isinstance(response, dict):
            return response
        # OpenAI SDK objects usually expose model_dump().
        model_dump = getattr(response, "model_dump", None)
        if callable(model_dump):
            dumped = model_dump()
            if isinstance(dumped, dict):
                return dumped
        return {}

    @staticmethod
    def _coerce_entities(value: Any) -> list[ExtractedEntity]:
        if not isinstance(value, list):
            return []
        out: list[ExtractedEntity] = []
        for item in value[:30]:
            if not isinstance(item, dict):
                continue
            try:
                out.append(ExtractedEntity.model_validate(item))
            except Exception:
                continue
        return out

    @staticmethod
    def _coerce_relations(value: Any) -> list[ExtractedRelation]:
        if not isinstance(value, list):
            return []
        out: list[ExtractedRelation] = []
        for item in value[:30]:
            if not isinstance(item, dict):
                continue
            try:
                out.append(ExtractedRelation.model_validate(item))
            except Exception:
                continue
        return out
