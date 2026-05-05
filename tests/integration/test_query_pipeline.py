"""Integration test: HTTP request → router → response.

We mock the inner ``QueryAgent.answer`` so this test runs hermetically (no
Neo4j, no LLM) but the wiring (FastAPI app → middleware → router → response
serialisation) is real.
"""

from __future__ import annotations

import myproject.router as router_mod
from fastapi.testclient import TestClient


class _FakeResponse:
    def __init__(self) -> None:
        self.answer = "Top co-occurrence: Alice ↔ Bob (4)."
        self.evidence = [{"from": "Alice", "to": "Bob", "freq": 4}]
        self.cypher = "MATCH (a)-[r]->(b) RETURN a, b, count(r) LIMIT 50"
        self.query_id = "q-int-001"
        self.warnings: list[str] = []


class _FakeAgent:
    def answer(self, _req):  # noqa: ANN001
        return _FakeResponse()


class _FakeSettings:
    query_llm_enabled = True
    query_llm_api_key = "fake"


def test_query_pipeline_end_to_end(monkeypatch) -> None:  # noqa: ANN001
    monkeypatch.setattr(router_mod, "_agent", lambda: (_FakeAgent(), _FakeSettings()))
    from myproject.api import app

    with TestClient(app) as client:
        response = client.post("/api/query", json={"text": "Who appears most?"})

    assert response.status_code == 200
    body = response.json()
    assert body["answer"]
    assert isinstance(body["citations"], list) and body["citations"]
    assert "doc_id" in body["citations"][0] and "snippet" in body["citations"][0]
    assert body["latency_ms"] >= 0
    assert body["cypher"]
    assert response.headers["X-Request-ID"].startswith("req_")
