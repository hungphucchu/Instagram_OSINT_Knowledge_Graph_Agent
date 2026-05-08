"""Generator — evidence-grounded answer synthesis.

The spec (``docs/SPEC.md`` §4.2) declares ``generate_answer(query, contexts)``.
Implementation delegates to ``agents.query.query_agent.QueryAgent`` for the
actual LLM call so behaviour stays in one place. When the LLM credential is
missing we still return a deterministic, grounded answer derived from the
contexts so the API can degrade without crashing.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from myproject.logging_setup import log_event

LOG = logging.getLogger("myproject.generator")


class ModelNotConfiguredError(RuntimeError):
    """Raised when the LLM credential required for synthesis is missing."""


def _deterministic_answer(query: str, contexts: list[dict[str, Any]]) -> str:
    if not contexts:
        return "No evidence found in the graph for this question."
    top = contexts[0]
    return f"Found {len(contexts)} evidence row(s) for '{query}'. Top row: " + json.dumps(
        top, ensure_ascii=False, default=str
    )


def generate_answer(
    query: str,
    contexts: list[dict[str, Any]],
    *,
    require_llm: bool = False,
) -> dict[str, Any]:
    """Return ``{answer, citations, latency_ms}``.

    ``require_llm=True`` raises :class:`ModelNotConfiguredError` when no
    credential is available — this is what powers the US-05 error story.
    """
    from agents.extraction.llm_client import LLMClient  # noqa: WPS433
    from config import get_settings  # noqa: WPS433

    settings = get_settings()
    citations = [
        {
            "doc_id": str(c.get("doc_id") or c.get("artifact_id") or i),
            "snippet": json.dumps(c, default=str)[:240],
        }
        for i, c in enumerate(contexts)
    ]
    if not (settings.query_llm_enabled and settings.query_llm_api_key):
        if require_llm:
            raise ModelNotConfiguredError("query LLM credential missing")
        log_event(LOG, "generator_llm_disabled_using_deterministic")
        return {
            "answer": _deterministic_answer(query, contexts),
            "citations": citations,
            "latency_ms": 0,
        }

    import time

    started = time.perf_counter()
    client = LLMClient(
        base_url=settings.query_llm_base_url,
        api_key=settings.query_llm_api_key,
        timeout_seconds=settings.query_llm_timeout_seconds,
        max_retries=0,
    )
    prompt = (
        "Write a short, user-friendly answer grounded ONLY in the evidence rows. "
        "Do not invent facts. If rows are empty say so explicitly.\n"
        f"Question: {query}\n"
        f"Evidence: {json.dumps(contexts, default=str)[:4000]}\n"
        'Output ONLY JSON: {"answer":"..."}'
    )
    try:
        resp = client.generate_json(
            model=settings.query_llm_model,
            messages=[
                {
                    "role": "system",
                    "content": "You synthesize grounded answers. Strict JSON only. /no_think",
                },
                {"role": "user", "content": prompt},
            ],
            temperature=0.0,
            max_tokens=256,
        )
        choices = (getattr(resp, "model_dump", lambda: resp)() or {}).get("choices") or []
        text = ""
        if choices:
            content = choices[0].get("message", {}).get("content") or ""
            if isinstance(content, list):
                text = "\n".join(part.get("text", "") for part in content if isinstance(part, dict))
            else:
                text = str(content)
        try:
            obj = json.loads(text)
            if isinstance(obj, dict) and isinstance(obj.get("answer"), str):
                answer = obj["answer"].strip()
            else:
                raise ValueError("no answer key")
        except Exception:
            answer = _deterministic_answer(query, contexts)
        latency_ms = int((time.perf_counter() - started) * 1000)
        log_event(LOG, "generator_llm_complete", latency_ms=latency_ms, characters=len(answer))
        return {"answer": answer, "citations": citations, "latency_ms": latency_ms}
    except Exception as exc:  # pragma: no cover - covered by integration mocks
        log_event(LOG, "generator_llm_failed", level=logging.WARNING, error=str(exc))
        return {
            "answer": _deterministic_answer(query, contexts),
            "citations": citations,
            "latency_ms": int((time.perf_counter() - started) * 1000),
        }
