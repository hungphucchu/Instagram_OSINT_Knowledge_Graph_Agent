"""Apify HTTP client with local request/response cache support."""

from __future__ import annotations

import json
from typing import Any, Callable
from urllib import error, request

from agents.collection.apify_cache_store import ApifyCacheStore


class ApifyClient:
    """Small Apify JSON client that reads/writes cache envelopes."""

    def __init__(self, api_token: str, cache_store: ApifyCacheStore) -> None:
        self._api_token = api_token
        self._cache_store = cache_store

    def post_json(
        self,
        endpoint: str,
        payload: dict[str, Any],
        *,
        use_cache: bool = True,
        timeout_seconds: int = 60,
    ) -> tuple[Any, bool]:
        """
        POST to Apify and return `(response_json, from_cache)`.

        Cached files are envelope objects; this method returns the `response` body.
        """
        if use_cache:
            envelope, from_cache = self._cache_store.get_or_fetch(
                endpoint=endpoint,
                payload=payload,
                fetcher=lambda ep, pl: self._fetch_post_json(
                    ep, pl, timeout_seconds=timeout_seconds
                ),
            )
            return envelope["response"], from_cache

        response = self._fetch_post_json(
            endpoint=endpoint,
            payload=payload,
            timeout_seconds=timeout_seconds,
        )
        return response, False

    def get_json(self, endpoint: str, *, timeout_seconds: int = 60) -> Any:
        """GET JSON from Apify API."""
        req = request.Request(
            url=f"https://api.apify.com{endpoint}",
            method="GET",
            headers={
                "Authorization": f"Bearer {self._api_token}",
            },
        )
        return self._execute_request(req=req, timeout_seconds=timeout_seconds)

    def fetch_json_with_cache(
        self,
        endpoint: str,
        payload: dict[str, Any],
        fetcher: Callable[[str, dict[str, Any]], Any],
    ) -> tuple[Any, bool]:
        """
        Resolve JSON via cache store with caller-provided fetcher.

        This is useful when a request requires multiple API calls but should still
        be cached under one deterministic request key.
        """
        envelope, from_cache = self._cache_store.get_or_fetch(
            endpoint=endpoint,
            payload=payload,
            fetcher=fetcher,
        )
        return envelope["response"], from_cache

    def _fetch_post_json(
        self,
        endpoint: str,
        payload: dict[str, Any],
        *,
        timeout_seconds: int,
    ) -> Any:
        body = json.dumps(payload).encode("utf-8")
        req = request.Request(
            url=f"https://api.apify.com{endpoint}",
            data=body,
            method="POST",
            headers={
                "Authorization": f"Bearer {self._api_token}",
                "Content-Type": "application/json",
            },
        )
        return self._execute_request(req=req, timeout_seconds=timeout_seconds)

    def _execute_request(self, *, req: request.Request, timeout_seconds: int) -> Any:
        try:
            with request.urlopen(req, timeout=timeout_seconds) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except error.HTTPError as exc:
            response_body = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(
                f"Apify request failed with status {exc.code}: {response_body}"
            ) from exc
