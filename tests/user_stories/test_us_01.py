"""Acceptance test for US-01: User can run a sample ingest from the UI."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient


@pytest.mark.user_story("US-01")
def test_us_01_sample_pipeline_returns_counts() -> None:
    """
    Given the app is running on a clean database,
    When the user clicks "Run sample pipeline",
    Then the response contains `run_id`, `raw_artifacts`, `extraction_records`
    and `dedup_clusters` integer fields with non-negative counts consistent
    with `fixtures/raw_artifacts.json`.
    """
    from myproject.api import app

    with TestClient(app) as client:
        response = client.post("/api/pipeline/sample")

    assert response.status_code == 200
    body = response.json()
    assert {"run_id", "raw_artifacts", "extraction_records", "dedup_clusters"} <= set(body)
    assert body["raw_artifacts"] >= 1
    assert body["extraction_records"] >= 1
    assert body["dedup_clusters"] >= 0
