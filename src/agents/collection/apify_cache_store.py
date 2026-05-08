"""Filesystem cache for Apify request/response envelopes."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


class ApifyCacheStore:
    """Caches Apify JSON responses keyed by endpoint + payload."""

    def __init__(self, cache_dir: Path) -> None:
        self._cache_dir = Path(cache_dir)
        self._cache_dir.mkdir(parents=True, exist_ok=True)

    def get(self, endpoint: str, payload: dict[str, Any]) -> dict[str, Any] | None:
        """Return cached JSON envelope when present."""
        path = self._cache_path(endpoint=endpoint, payload=payload)
        if not path.is_file():
            return None
        return json.loads(path.read_text(encoding="utf-8"))

    def put(
        self, endpoint: str, payload: dict[str, Any], response: Any
    ) -> dict[str, Any]:
        """Persist a request/response envelope and return it."""
        cache_key = self._cache_key(endpoint=endpoint, payload=payload)
        envelope: dict[str, Any] = {
            "cache_key": cache_key,
            "created_at": datetime.now(UTC).isoformat(),
            "request": {"endpoint": endpoint, "payload": payload},
            "response": response,
        }
        path = self._cache_dir / f"{cache_key}.json"
        path.write_text(json.dumps(envelope, indent=2, sort_keys=True), encoding="utf-8")
        return envelope

    def get_or_fetch(
        self,
        endpoint: str,
        payload: dict[str, Any],
        fetcher: Callable[[str, dict[str, Any]], Any],
    ) -> tuple[dict[str, Any], bool]:
        """
        Get cached envelope or fetch fresh response and cache it.

        Returns `(envelope, from_cache)`.
        """
        cached = self.get(endpoint=endpoint, payload=payload)
        if cached is not None:
            return cached, True

        response = fetcher(endpoint, payload)
        if not self._is_cacheable_response(response):
            envelope = {
                "cache_key": self._cache_key(endpoint=endpoint, payload=payload),
                "created_at": datetime.now(UTC).isoformat(),
                "request": {"endpoint": endpoint, "payload": payload},
                "response": response,
            }
            return envelope, False

        envelope = self.put(endpoint=endpoint, payload=payload, response=response)
        return envelope, False

    def _cache_path(self, endpoint: str, payload: dict[str, Any]) -> Path:
        return self._cache_dir / f"{self._cache_key(endpoint=endpoint, payload=payload)}.json"

    @staticmethod
    def _cache_key(endpoint: str, payload: dict[str, Any]) -> str:
        canonical = json.dumps(
            {"endpoint": endpoint, "payload": payload},
            sort_keys=True,
            separators=(",", ":"),
        )
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    @staticmethod
    def _is_cacheable_response(response: Any) -> bool:
        """Cache only non-empty, non-error response objects."""
        if response in (None, {}):
            return False

        if not isinstance(response, dict):
            return True

        status = str(response.get("status", "")).lower()
        if status in {"error", "fail", "failed"}:
            return False

        return not ("error" in response or "errors" in response)
