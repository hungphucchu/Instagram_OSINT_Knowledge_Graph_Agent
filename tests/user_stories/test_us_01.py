"""Acceptance test for US-01: User submits a query and receives a cited answer."""

from __future__ import annotations

import myproject.router as router_mod
import pytest
from fastapi.testclient import TestClient


class _FakeResponse:
    def __init__(self) -> None:
        self.answer = "Most frequent co-occurrence: Alice ↔ Bob (4)."
        self.evidence = [
            {"doc_id": "post-1", "from": "Alice", "to": "Bob", "freq": 4},
            {"doc_id": "post-2", "from": "Alice", "to": "Carol", "freq": 2},
        ]
        self.cypher = "MATCH (a)-[r]->(b) RETURN a, b, count(r) AS f LIMIT 50"
        self.query_id = "q-us01"
        self.warnings: list[str] = []


class _FakeAgent:
    def answer(self, _req):  # noqa: ANN001
        return _FakeResponse()


class _FakeSettings:
    query_llm_enabled = True
    query_llm_api_key = "fake"


@pytest.mark.user_story("US-01")
def test_us_01_query_returns_cited_answer(monkeypatch: pytest.MonkeyPatch) -> None:
    """
    Given the application is running and the Neo4j graph is reachable,
    When the user submits the query "Who appeared together most often?",
    Then the response contains a non-empty `answer` string, at least one
    citation with a `doc_id` and `snippet`, the `latency_ms` is reported,
    and the executed Cypher is returned in `cypher`.
    """
    monkeypatch.setattr(router_mod, "_agent", lambda: (_FakeAgent(), _FakeSettings()))
    from myproject.api import app

    with TestClient(app) as client:
        response = client.post(
            "/api/query",
            json={"text": "Who appeared together most often?", "max_results": 5},
        )

    assert response.status_code == 200
    body = response.json()
    assert body["answer"].strip() != ""
    assert isinstance(body["citations"], list)
    assert len(body["citations"]) >= 1
    for citation in body["citations"]:
        assert "doc_id" in citation
        assert "snippet" in citation
    assert isinstance(body["latency_ms"], int)
    assert body["cypher"] and body["cypher"].lstrip().upper().startswith("MATCH")
