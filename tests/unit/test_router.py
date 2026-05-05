"""Unit tests for ``src/myproject/router.py``.

These tests cover the public contract (``EmptyInputError``, ``route_query``)
and the row-summarising helper without ever touching Neo4j or the LLM.
"""

from __future__ import annotations

import myproject.router as router_mod
import pytest
from myproject.generator import ModelNotConfiguredError
from myproject.router import EmptyInputError, route_query


class _FakeResponse:
    def __init__(self) -> None:
        self.answer = "Most frequent mention is Alice -> Bob."
        self.evidence = [
            {"from_name": "Alice", "to_name": "Bob", "freq": 4, "node_id": "n1"},
            {"from_name": "Alice", "to_name": "Carol", "freq": 2, "node_id": "n2"},
        ]
        self.cypher = "MATCH (a)-[r]->(b) RETURN a, b, count(r) LIMIT 50"
        self.query_id = "q-test-001"
        self.warnings: list[str] = []


class _FakeAgent:
    def answer(self, _req):  # noqa: ANN001
        return _FakeResponse()


class _FakeSettings:
    query_llm_enabled = True
    query_llm_api_key = "fake-key"


@pytest.fixture
def patched_agent(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(router_mod, "_agent", lambda: (_FakeAgent(), _FakeSettings()))
    yield


def test_router_module_imports() -> None:
    """Sanity: the module imports cleanly without side-effects."""
    import myproject.router  # noqa: F401


def test_route_query_rejects_empty_input(patched_agent: None) -> None:
    with pytest.raises(EmptyInputError):
        route_query("   ")


def test_route_query_returns_expected_shape(patched_agent: None) -> None:
    result = route_query("Who appeared together most often?", max_results=5)
    assert isinstance(result, dict)
    assert result["answer"].strip() != ""
    assert isinstance(result["citations"], list)
    assert len(result["citations"]) >= 1
    for citation in result["citations"]:
        assert "doc_id" in citation
        assert "snippet" in citation
    assert isinstance(result["latency_ms"], int)
    assert result["latency_ms"] >= 0
    assert result["cypher"]
    assert result["query_id"]


def test_route_query_caps_citations_to_max_results(patched_agent: None) -> None:
    result = route_query("anything", max_results=1)
    assert len(result["citations"]) == 1


def test_route_query_raises_when_llm_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    def _raise() -> None:
        raise ModelNotConfiguredError("query LLM credential missing")

    monkeypatch.setattr(router_mod, "_agent", _raise)
    with pytest.raises(ModelNotConfiguredError):
        route_query("hello")


def test_summarise_row_truncates_long_values() -> None:
    row = {"long": "x" * 500, "short": "abc"}
    snippet = router_mod._summarise_row(row)
    assert "long=" in snippet
    assert "..." in snippet  # truncation marker
    assert len(snippet) < 260
