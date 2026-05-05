"""Phase 1 — Apify cache behavior."""

from __future__ import annotations

from pathlib import Path

from agents.collection import ApifyCacheStore, ApifyClient
from config import Settings


def test_apify_cache_store_get_or_fetch_uses_cache_after_first_call(tmp_path: Path) -> None:
    store = ApifyCacheStore(cache_dir=tmp_path / "apify_cache")
    calls = {"count": 0}

    def fetcher(endpoint: str, payload: dict[str, object]) -> dict[str, object]:
        calls["count"] += 1
        return {"endpoint": endpoint, "payload": payload, "ok": True}

    endpoint = "/v2/test"
    payload = {"actorId": "abc", "limit": 3}

    envelope_1, from_cache_1 = store.get_or_fetch(
        endpoint=endpoint, payload=payload, fetcher=fetcher
    )
    envelope_2, from_cache_2 = store.get_or_fetch(
        endpoint=endpoint, payload=payload, fetcher=fetcher
    )

    assert from_cache_1 is False
    assert from_cache_2 is True
    assert calls["count"] == 1
    assert envelope_1["response"] == envelope_2["response"]


def test_apify_client_reads_from_cache(tmp_path: Path) -> None:
    class FakeApifyClient(ApifyClient):
        def _fetch_post_json(
            self,
            endpoint: str,
            payload: dict[str, object],
            *,
            timeout_seconds: int,
        ) -> dict[str, object]:
            self.fetch_count += 1
            return {"endpoint": endpoint, "payload": payload, "source": "network"}

    store = ApifyCacheStore(cache_dir=tmp_path / "apify_cache")
    client = FakeApifyClient(api_token="token", cache_store=store)
    client.fetch_count = 0

    endpoint = "/v2/acts/demo/runs"
    payload = {"input": {"username": "public_profile"}}

    response_1, from_cache_1 = client.post_json(endpoint=endpoint, payload=payload)
    response_2, from_cache_2 = client.post_json(endpoint=endpoint, payload=payload)

    assert response_1 == response_2
    assert from_cache_1 is False
    assert from_cache_2 is True
    assert client.fetch_count == 1


def test_settings_default_apify_cache_dir() -> None:
    settings = Settings()
    assert settings.apify_cache_dir.name == "apify_cache"


def test_apify_cache_store_does_not_cache_empty_or_error_response(tmp_path: Path) -> None:
    store = ApifyCacheStore(cache_dir=tmp_path / "apify_cache")
    endpoint = "/v2/test"
    payload = {"actorId": "abc", "limit": 3}

    calls = {"count": 0}

    def empty_fetcher(_endpoint: str, _payload: dict[str, object]) -> dict[str, object]:
        calls["count"] += 1
        return {}

    _envelope_1, from_cache_1 = store.get_or_fetch(
        endpoint=endpoint, payload=payload, fetcher=empty_fetcher
    )
    _envelope_2, from_cache_2 = store.get_or_fetch(
        endpoint=endpoint, payload=payload, fetcher=empty_fetcher
    )
    assert from_cache_1 is False
    assert from_cache_2 is False
    assert calls["count"] == 2

    def error_fetcher(_endpoint: str, _payload: dict[str, object]) -> dict[str, object]:
        calls["count"] += 1
        return {"status": "fail", "error": "bad request"}

    _envelope_3, from_cache_3 = store.get_or_fetch(
        endpoint=endpoint, payload=payload, fetcher=error_fetcher
    )
    _envelope_4, from_cache_4 = store.get_or_fetch(
        endpoint=endpoint, payload=payload, fetcher=error_fetcher
    )
    assert from_cache_3 is False
    assert from_cache_4 is False
    assert calls["count"] == 4
