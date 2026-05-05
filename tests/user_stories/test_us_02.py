"""Acceptance test for US-02 [ERROR PATH]: Empty input shows an actionable error."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient


@pytest.mark.user_story("US-02")
def test_us_02_empty_input_returns_error() -> None:
    """
    Given the application is running,
    When the user clicks Submit without typing anything,
    Then an inline error message appears stating "Please enter a question",
    and `POST /api/query` returns 400 `{"error": "input text is required"}`.
    """
    from myproject.api import app

    with TestClient(app) as client:
        response = client.post("/api/query", json={"text": ""})

    assert response.status_code == 400
    body = response.json()
    assert "input text is required" in body.get("error", "").lower()
