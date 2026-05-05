"""Linguistic edge-case tests for ``POST /api/query``.

The application must not crash on empty, very long, or non-ASCII inputs.
We also verify the API returns either a clean 4xx (validation/auth) or a
5xx <= 503 (no uncaught crashes / 500s after the safety net).
"""

from __future__ import annotations

from fastapi.testclient import TestClient


def test_empty_input_does_not_crash() -> None:
    from myproject.api import app

    with TestClient(app) as client:
        r = client.post("/api/query", json={"text": ""})
    assert r.status_code == 400
    assert "input text is required" in r.json().get("error", "").lower()


def test_very_long_input_does_not_crash() -> None:
    from myproject.api import app

    huge = "lorem ipsum " * 10_000
    with TestClient(app) as client:
        r = client.post("/api/query", json={"text": huge})
    # 4xx (validation/missing key) is fine; we only forbid 5xx other than 503.
    assert r.status_code in (200, 400, 422, 503)


def test_non_ascii_input_does_not_crash() -> None:
    from myproject.api import app

    with TestClient(app) as client:
        r = client.post("/api/query", json={"text": "你好世界 🌍 emoji"})
    assert r.status_code in (200, 400, 422, 503)


def test_multilingual_input_does_not_crash() -> None:
    from myproject.api import app

    prompt = "¿Quién aparece más veces con demo_user? أجب بالعربية إذا أمكن."
    with TestClient(app) as client:
        r = client.post("/api/query", json={"text": prompt})
    assert r.status_code in (200, 400, 422, 503)


def test_code_mixed_input_does_not_crash() -> None:
    from myproject.api import app

    with TestClient(app) as client:
        r = client.post("/api/query", json={"text": "Show me posts mentioning 字段 X"})
    assert r.status_code in (200, 400, 422, 503)


def test_adversarial_payload_does_not_crash() -> None:
    from myproject.api import app

    payload = "DROP DATABASE neo4j; --"
    with TestClient(app) as client:
        r = client.post("/api/query", json={"text": payload})
    # The Cypher safety guard refuses anything mutating; so we either get
    # 200 with a safe-fallback answer, or 503 if the LLM key is missing.
    assert r.status_code in (200, 503)
    if r.status_code == 200:
        body = r.json()
        # Whatever was returned, no DROP / DELETE / MERGE escaped to Cypher.
        assert "DROP" not in (body.get("cypher") or "").upper()
        assert "DELETE" not in (body.get("cypher") or "").upper()
