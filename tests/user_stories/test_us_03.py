"""Acceptance test for US-03 [ERROR PATH]: Missing LLM API key returns 503."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient


@pytest.mark.user_story("US-03")
def test_us_03_missing_api_key_returns_503(monkeypatch: pytest.MonkeyPatch) -> None:
    """
    Given the application is running with `QUERY_LLM_API_KEY` empty,
    When the user submits any non-empty question,
    Then the response shows "The model service is not configured. Contact the
    operator." and the HTTP status is 503 (not 500), and no Python stack
    trace appears in the response body.
    """
    # The autouse conftest already disables the LLM credential, but we re-set
    # explicitly to make the intent of this story crystal clear.
    monkeypatch.setenv("QUERY_LLM_ENABLED", "true")  # enabled but no key
    monkeypatch.setenv("QUERY_LLM_API_KEY", "")
    from config import get_settings

    get_settings.cache_clear()

    from myproject.api import app

    with TestClient(app) as client:
        response = client.post("/api/query", json={"text": "hello"})

    assert response.status_code == 503
    body = response.json()
    assert "not configured" in body.get("error", "").lower()
    assert "operator" in body.get("error", "").lower()
    # No Python traceback leaked
    assert "Traceback" not in response.text
