"""Unit test for ``src/myproject/api.py``.

We don't spin up an HTTP client here (that lives in tests/integration); we
only verify that importing the module wires the FastAPI app and exposes the
expected routes.
"""

from __future__ import annotations


def test_api_module_imports_and_exposes_routes() -> None:
    from myproject.api import app

    paths = {route.path for route in app.routes}
    assert "/health" in paths
    assert "/api/query" in paths
    assert "/api/stats" in paths
    assert "/api/pipeline/sample" in paths
    assert "/" in paths


def test_health_endpoint_returns_ok() -> None:
    from fastapi.testclient import TestClient
    from myproject.api import app

    with TestClient(app) as client:
        r = client.get("/health")
    assert r.status_code == 200
    assert r.text.strip() == "ok"
    assert r.headers.get("X-Request-ID", "").startswith("req_")
