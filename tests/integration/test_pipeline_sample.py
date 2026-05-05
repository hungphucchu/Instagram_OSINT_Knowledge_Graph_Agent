"""Integration test: ``POST /api/pipeline/sample`` runs the sample ingest end-to-end.

Uses the bundled fixture under ``fixtures/raw_artifacts.json`` and the
isolated SQLite stores set up by ``tests/conftest.py``.
"""

from __future__ import annotations

from fastapi.testclient import TestClient


def test_post_sample_pipeline_returns_counts() -> None:
    from myproject.api import app

    with TestClient(app) as client:
        response = client.post("/api/pipeline/sample")

    assert response.status_code == 200
    body = response.json()
    assert "run_id" in body
    assert isinstance(body["raw_artifacts"], int)
    assert body["raw_artifacts"] >= 1
    assert isinstance(body["extraction_records"], int)
    assert body["extraction_records"] >= 1
    assert isinstance(body["dedup_clusters"], int)
    assert body["dedup_clusters"] >= 0
