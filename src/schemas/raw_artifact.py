"""Minimal raw artifact shape for Phase 1 collection (validated against fixtures in Phase 0)."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class RawArtifact(BaseModel):
    """Synthetic or collected Instagram-style public post payload."""

    model_config = ConfigDict(extra="forbid")

    artifact_id: str
    source_url: str
    platform_post_id: str
    caption_text: str
    collected_at: datetime
    run_id: str
    collector_version: str
    adapter_id: str
    hashtags: list[str] = Field(default_factory=list)
    mentions: list[str] = Field(default_factory=list)
    raw_payload: dict[str, Any] = Field(default_factory=dict)
    extractor_model: str | None = None
    snippet_hash: str | None = None
    ingested_at: datetime | None = None
