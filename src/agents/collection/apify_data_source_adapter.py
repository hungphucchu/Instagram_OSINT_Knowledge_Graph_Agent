"""File-backed adapter for previously downloaded Apify dataset JSON."""

from __future__ import annotations

import hashlib
import json
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from schemas.raw_artifact import RawArtifact

from agents.collection.fetch_limits import clamp_fetch_count
from agents.collection.models import CollectionRunConfig
from agents.collection.source_adapter import SourceAdapter

_HASHTAG_RE = re.compile(r"#([A-Za-z0-9_]+)")
_MENTION_RE = re.compile(r"@([A-Za-z0-9._]+)")


class ApifyDataSourceAdapter(SourceAdapter):
    """Loads Apify dataset export from disk and maps into RawArtifact rows."""

    def __init__(self, dataset_path: Path) -> None:
        self._dataset_path = Path(dataset_path)

    @property
    def adapter_id(self) -> str:
        return "apify_data"

    def fetch(self, config: CollectionRunConfig) -> list[RawArtifact]:
        items = self._read_items()
        n = clamp_fetch_count(len(items), config.max_items)
        artifacts = [self._item_to_artifact(item=item, config=config) for item in items[:n]]
        return artifacts

    def _read_items(self) -> list[dict[str, Any]]:
        payload = json.loads(self._dataset_path.read_text(encoding="utf-8"))
        if isinstance(payload, list):
            return [x for x in payload if isinstance(x, dict)]
        if isinstance(payload, dict):
            items = payload.get("items")
            if isinstance(items, list):
                return [x for x in items if isinstance(x, dict)]
        raise ValueError(f"Unsupported Apify dataset JSON shape: {self._dataset_path}")

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
        collected_at = self._parse_collected_at(item.get("timestamp"))

        stable = hashlib.sha256(
            f"{platform_post_id}:{source_url}:{config.run_id}".encode()
        ).hexdigest()[:24]
        return RawArtifact(
            artifact_id=f"apifydata-{stable}",
            source_url=source_url,
            platform_post_id=platform_post_id,
            caption_text=caption_text,
            collected_at=collected_at,
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
    def _parse_collected_at(value: Any) -> datetime:
        if isinstance(value, str):
            normalized = value.replace("Z", "+00:00")
            try:
                return datetime.fromisoformat(normalized)
            except ValueError:
                pass
        return datetime.now(UTC)
