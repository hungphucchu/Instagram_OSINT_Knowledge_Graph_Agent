"""Unit tests for ``src/myproject/generator.py``."""

from __future__ import annotations

import pytest
from myproject.generator import ModelNotConfiguredError, generate_answer


def test_generator_module_imports() -> None:
    import myproject.generator  # noqa: F401


def test_generate_answer_no_contexts_returns_no_evidence() -> None:
    result = generate_answer("anything", contexts=[])
    assert "No evidence" in result["answer"]
    assert result["citations"] == []
    assert result["latency_ms"] >= 0


def test_generate_answer_deterministic_when_llm_disabled() -> None:
    contexts = [{"doc_id": "post-1", "snippet": "hello"}, {"doc_id": "post-2"}]
    result = generate_answer("who?", contexts=contexts)
    assert "Found 2 evidence row(s)" in result["answer"]
    assert len(result["citations"]) == 2
    for c in result["citations"]:
        assert "doc_id" in c
        assert "snippet" in c


def test_generate_answer_require_llm_raises_when_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("QUERY_LLM_ENABLED", "false")
    monkeypatch.setenv("QUERY_LLM_API_KEY", "")
    from config import get_settings

    get_settings.cache_clear()
    with pytest.raises(ModelNotConfiguredError):
        generate_answer("who?", contexts=[{"a": 1}], require_llm=True)
