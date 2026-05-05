"""Acceptance test for US-05: User can inspect graph statistics."""

from __future__ import annotations

import myproject.api as api_mod
import pytest
from fastapi.testclient import TestClient


class _FakeRetriever:
    def graph_stats(self) -> dict[str, int]:
        return {"nodes": 12, "edges": 9}

    def close(self) -> None:
        pass


@pytest.mark.user_story("US-05")
def test_us_05_graph_stats(monkeypatch: pytest.MonkeyPatch) -> None:
    """
    Given the app is running and connected to Neo4j,
    When the user clicks "Refresh graph stats",
    Then the response contains `version`, `nodes`, and `edges` integer fields,
    and `GET /api/stats` returns 200.
    """
    # Patch the Retriever symbol the API imports so the test does not need a
    # live Neo4j server.
    monkeypatch.setattr("myproject.retriever.Retriever", _FakeRetriever)
    with TestClient(api_mod.app) as client:
        response = client.get("/api/stats")

    assert response.status_code == 200
    body = response.json()
    assert "version" in body
    assert isinstance(body["nodes"], int)
    assert isinstance(body["edges"], int)
    assert body["nodes"] == 12
    assert body["edges"] == 9
