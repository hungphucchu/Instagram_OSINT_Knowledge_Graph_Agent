"""Optional LLM-based quality judge over extraction samples."""

from __future__ import annotations

import json
import logging
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from typing import Any

from agents.extraction.llm_client import LLMClient
from schemas.extraction_record import ExtractionRecord
from schemas.quality_report import QualityViolation, SuggestedFix
from schemas.raw_artifact import RawArtifact


@dataclass(frozen=True)
class JudgeSample:
    artifact: RawArtifact
    extraction: ExtractionRecord


class QualityLLMJudge:
    """Turns sampled extraction disagreements into structured quality violations."""

    def __init__(
        self,
        *,
        provider: str,
        model_id: str,
        base_url: str,
        api_key: str,
        timeout_seconds: int,
        max_samples: int,
        max_concurrency: int,
        score_threshold: float,
    ) -> None:
        self._provider = provider
        self._model_id = model_id
        self._base_url = base_url.rstrip("/")
        self._api_key = api_key
        self._timeout_seconds = timeout_seconds
        self._max_samples = max(0, max_samples)
        self._max_concurrency = max(1, max_concurrency)
        self._score_threshold = max(0.0, min(1.0, score_threshold))
        self._llm_disabled = False
        self._log = logging.getLogger("quality.llm_judge")
        self._client = LLMClient(
            base_url=self._base_url,
            api_key=api_key,
            timeout_seconds=self._timeout_seconds,
            max_retries=0,
        )

    @property
    def enabled(self) -> bool:
        return bool(self._api_key and self._max_samples > 0 and not self._llm_disabled)

    def evaluate(self, pairs: list[JudgeSample]) -> list[QualityViolation]:
        if not self._api_key or self._max_samples <= 0:
            return []
        if not pairs:
            return []
        violations: list[QualityViolation] = []
        sample_batch = pairs[: self._max_samples]
        with ThreadPoolExecutor(max_workers=self._max_concurrency) as executor:
            futures = {executor.submit(self._evaluate_one, sample): sample.artifact.artifact_id for sample in sample_batch}
            for future in as_completed(futures):
                item = future.result()
                if item is not None:
                    violations.append(item)
        return violations

    def _evaluate_one(self, sample: JudgeSample) -> QualityViolation | None:
        try:
            verdict = self._judge_one(sample)
            if verdict["pass"] is True:
                return None
            score = verdict["score"]
            if score >= self._score_threshold and verdict["issues"]:
                return None
            suggested = []
            for issue in verdict["issues"][:3]:
                suggested_fix = issue.get("suggested_fix")
                if suggested_fix:
                    suggested.append(
                        SuggestedFix(
                            action="review_extraction",
                            detail=json.dumps(suggested_fix, ensure_ascii=True),
                            entity_ids=[],
                        )
                    )
            return QualityViolation(
                rule_id="llm_judge_extraction_mismatch",
                severity="warning",
                message="LLM judge flags extraction inconsistency against source text",
                sample_ids=[sample.artifact.artifact_id],
                metadata={
                    "provider": self._provider,
                    "model_id": self._model_id,
                    "score": score,
                    "issues": verdict["issues"][:5],
                },
                suggested_fixes=suggested,
            )
        except KeyboardInterrupt:
            raise
        except Exception as exc:
            name = type(exc).__name__
            if self._is_transport_error(exc):
                self._llm_disabled = True
                self._log.warning(
                    "quality_llm_transport_error_disable artifact_id=%s provider=%s model=%s err=%s",
                    sample.artifact.artifact_id,
                    self._provider,
                    self._model_id,
                    name,
                )
            else:
                self._log.warning(
                    "quality_llm_parse_error_skip artifact_id=%s provider=%s model=%s err=%s",
                    sample.artifact.artifact_id,
                    self._provider,
                    self._model_id,
                    name,
                )
            return None

    def _judge_one(self, sample: JudgeSample) -> dict[str, Any]:
        payload = self._build_payload(sample)
        response = self._client.generate_json(
            model=payload["model"],
            messages=payload["messages"],
            temperature=payload["temperature"],
            max_tokens=payload["max_tokens"],
        )
        return self._parse_response_json(response)

    def _build_payload(self, sample: JudgeSample) -> dict[str, Any]:
        prompt = {
            "artifact_id": sample.artifact.artifact_id,
            "source_text": self._truncate(sample.artifact.caption_text, 1500),
            "mentions": sample.artifact.mentions,
            "hashtags": sample.artifact.hashtags,
            "extracted_entities": [e.model_dump(mode="json") for e in sample.extraction.entities],
            "extracted_relations": [r.model_dump(mode="json") for r in sample.extraction.relations],
        }
        system = (
            "You are a strict extraction quality judge. "
            "Output valid JSON only, no explanations, no <think> blocks. /no_think"
        )
        user = (
            "Evaluate whether extraction matches source text. "
            "Return STRICT JSON ONLY with keys: pass, score, issues.\n"
            "pass: boolean\n"
            "score: number between 0 and 1 (higher means better extraction)\n"
            "issues: array of objects with keys: type, reason, evidence_span, suggested_fix(optional)\n\n"
            f"Input JSON:\n{json.dumps(prompt, ensure_ascii=True)}"
        )
        return {
            "model": self._model_id,
            "temperature": 0.0,
            "max_tokens": 1200,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        }

    def _parse_response_json(self, response: Any) -> dict[str, Any]:
        response_dict = self._response_to_dict(response)
        choices = response_dict.get("choices")
        if not isinstance(choices, list) or not choices:
            return {"pass": True, "score": 1.0, "issues": []}
        message = choices[0].get("message", {})
        content = self._extract_message_content(message)
        if not content.strip():
            return {"pass": True, "score": 1.0, "issues": []}
        parsed = self._parse_json_content(content)
        if not isinstance(parsed, dict):
            return {"pass": True, "score": 1.0, "issues": []}
        return self._coerce_verdict(parsed)

    @staticmethod
    def _response_to_dict(response: Any) -> dict[str, Any]:
        if isinstance(response, dict):
            return response
        dump = getattr(response, "model_dump", None)
        if callable(dump):
            out = dump()
            if isinstance(out, dict):
                return out
        return {}

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
        text = QualityLLMJudge._strip_reasoning_tags(text)
        if text.startswith("```"):
            lines = text.splitlines()
            if len(lines) >= 3 and lines[0].startswith("```") and lines[-1].startswith("```"):
                text = "\n".join(lines[1:-1]).strip()
            if text.lower().startswith("json\n"):
                text = text.split("\n", 1)[1]
        try:
            return json.loads(text)
        except Exception:
            pass
        candidate = QualityLLMJudge._extract_first_json_object(text)
        if candidate is not None:
            try:
                return json.loads(candidate)
            except Exception:
                pass
        salvaged = QualityLLMJudge._salvage_truncated_json(text)
        if salvaged is not None:
            return salvaged
        raise ValueError("No parsable JSON object found in judge output")

    @staticmethod
    def _coerce_verdict(parsed: dict[str, Any]) -> dict[str, Any]:
        raw_issues = parsed.get("issues")
        issues: list[dict[str, Any]] = []
        if isinstance(raw_issues, list):
            for item in raw_issues[:20]:
                if isinstance(item, dict):
                    issues.append(item)
        raw_score = parsed.get("score")
        try:
            score = float(raw_score)
        except (TypeError, ValueError):
            score = 1.0 if not issues else 0.0
        score = max(0.0, min(1.0, score))
        raw_pass = parsed.get("pass")
        if isinstance(raw_pass, bool):
            passed = raw_pass
        else:
            passed = not issues
        return {"pass": passed, "score": score, "issues": issues}

    @staticmethod
    def _truncate(text: str, limit: int) -> str:
        if len(text) <= limit:
            return text
        return text[:limit] + "..."

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

    @staticmethod
    def _strip_reasoning_tags(text: str) -> str:
        text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL | re.IGNORECASE).strip()
        open_tag = re.search(r"<think>", text, flags=re.IGNORECASE)
        close_tag = re.search(r"</think>", text, flags=re.IGNORECASE)
        if open_tag and not close_tag:
            text = text[: open_tag.start()].strip()
        return text

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
