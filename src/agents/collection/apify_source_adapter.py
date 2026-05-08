"""Apify-backed SourceAdapter for live Phase 1 collection."""

from __future__ import annotations

import hashlib
import re
import time
from datetime import UTC, datetime
from typing import Any

from schemas.raw_artifact import RawArtifact

from agents.collection.apify_client import ApifyClient
from agents.collection.fetch_limits import clamp_fetch_count
from agents.collection.models import CollectionRunConfig
from agents.collection.source_adapter import SourceAdapter

_HASHTAG_RE = re.compile(r"#([A-Za-z0-9_]+)")
_MENTION_RE = re.compile(r"@([A-Za-z0-9._]+)")


class ApifySourceAdapter(SourceAdapter):
    """Fetches public Instagram-like items via a configured Apify Actor."""

    def __init__(
        self,
        client: ApifyClient,
        actor_id: str,
        *,
        run_timeout_seconds: int = 300,
        poll_interval_seconds: int = 5,
    ) -> None:
        self._client = client
        self._actor_id = actor_id
        self._run_timeout_seconds = run_timeout_seconds
        self._poll_interval_seconds = poll_interval_seconds

    @property
    def adapter_id(self) -> str:
        return "apify"

    def fetch(self, config: CollectionRunConfig) -> list[RawArtifact]:
        endpoint = f"/v2/acts/{self._actor_path_id()}/runs-async-dataset-items"
        # Apify rejects unbounded maxItems; large cap when user requests "all" (max_items <= 0).
        api_max_items = config.max_items if config.max_items > 0 else 50_000
        payload: dict[str, Any] = {"maxItems": api_max_items}
        if config.seed_handles:
            payload["directUrls"] = [f"https://www.instagram.com/{h}/" for h in config.seed_handles]

        response, _from_cache = self._client.fetch_json_with_cache(
            endpoint=endpoint,
            payload=payload,
            fetcher=self._run_actor_and_fetch_dataset_items,
        )
        items = self._extract_items(response)
        n = clamp_fetch_count(len(items), config.max_items)
        artifacts = [self._item_to_artifact(item=item, config=config) for item in items[:n]]
        return artifacts

    def _run_actor_and_fetch_dataset_items(
        self, _endpoint: str, payload: dict[str, Any]
    ) -> list[dict[str, Any]]:
        actor_runs_endpoint = f"/v2/acts/{self._actor_path_id()}/runs"
        run_response, _ = self._client.post_json(
            endpoint=actor_runs_endpoint,
            payload=payload,
            use_cache=False,
            timeout_seconds=60,
        )
        run_id = self._extract_run_id(run_response)
        if not run_id:
            raise RuntimeError("Apify run did not return run id")

        run_data = self._poll_run_until_terminal(run_id=run_id)
        status = str(run_data.get("status", "")).upper()
        if status != "SUCCEEDED":
            raise RuntimeError(f"Apify run failed with status={status}")

        dataset_id = run_data.get("defaultDatasetId")
        if not dataset_id:
            raise RuntimeError("Apify run succeeded but defaultDatasetId is missing")

        dataset_endpoint = f"/v2/datasets/{dataset_id}/items?clean=true&format=json"
        dataset_items = self._client.get_json(dataset_endpoint, timeout_seconds=120)
        return self._extract_items(dataset_items)

    def _actor_path_id(self) -> str:
        """
        Normalize actor id for URL path usage.

        Apify Store IDs are commonly `owner/actor-name`, while REST path form
        is `owner~actor-name`.
        """
        return self._actor_id.replace("/", "~")

    def _extract_items(self, response: Any) -> list[dict[str, Any]]:
        if isinstance(response, list):
            return [x for x in response if isinstance(x, dict)]
        if isinstance(response, dict):
            items = response.get("items")
            if isinstance(items, list):
                return [x for x in items if isinstance(x, dict)]
        return []

    def _item_to_artifact(self, *, item: dict[str, Any], config: CollectionRunConfig) -> RawArtifact:
        platform_post_id = str(
            item.get("platform_post_id")
            or item.get("id")
            or item.get("shortCode")
            or item.get("shortcode")
            or "unknown"
        )
        source_url = str(
            item.get("source_url")
            or item.get("permalink")
            or item.get("url")
            or f"https://www.instagram.com/p/{platform_post_id}/"
        )
        caption_text = str(item.get("caption_text") or item.get("caption") or "")
        hashtags = self._normalized_list(item.get("hashtags")) or _HASHTAG_RE.findall(caption_text)
        mentions = self._normalized_list(item.get("mentions")) or _MENTION_RE.findall(caption_text)

        stable = hashlib.sha256(
            f"{platform_post_id}:{source_url}:{config.run_id}".encode()
        ).hexdigest()[:24]
        return RawArtifact(
            artifact_id=f"apify-{stable}",
            source_url=source_url,
            platform_post_id=platform_post_id,
            caption_text=caption_text,
            collected_at=datetime.now(UTC),
            run_id=config.run_id,
            collector_version=config.collector_version,
            adapter_id=self.adapter_id,
            hashtags=hashtags,
            mentions=mentions,
            raw_payload=item,
        )

    @staticmethod
    def _normalized_list(value: Any) -> list[str]:
        if not isinstance(value, list):
            return []
        return [str(v).strip() for v in value if str(v).strip()]

    @staticmethod
    def _extract_run_id(run_response: Any) -> str | None:
        if not isinstance(run_response, dict):
            return None
        data = run_response.get("data")
        if isinstance(data, dict):
            run_id = data.get("id")
            return str(run_id) if run_id else None
        run_id = run_response.get("id")
        return str(run_id) if run_id else None

    def _poll_run_until_terminal(self, *, run_id: str) -> dict[str, Any]:
        started = time.monotonic()
        while True:
            run_endpoint = f"/v2/actor-runs/{run_id}"
            run_response = self._client.get_json(run_endpoint, timeout_seconds=30)
            run_data = self._extract_run_data(run_response)
            status = str(run_data.get("status", "")).upper()
            if status in {"SUCCEEDED", "FAILED", "ABORTED", "TIMED-OUT"}:
                return run_data

            if time.monotonic() - started >= self._run_timeout_seconds:
                raise RuntimeError(
                    f"Apify run polling timed out after {self._run_timeout_seconds}s (run_id={run_id})"
                )
            time.sleep(self._poll_interval_seconds)

    @staticmethod
    def _extract_run_data(run_response: Any) -> dict[str, Any]:
        if not isinstance(run_response, dict):
            return {}
        data = run_response.get("data")
        if isinstance(data, dict):
            return data
        return run_response
