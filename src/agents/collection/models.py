"""Data models for Phase 1 collection orchestration."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Literal


@dataclass(frozen=True)
class CollectionRunConfig:
    """Configuration passed to SourceAdapters for one collection run."""

    run_id: str
    collector_version: str
    max_items: int = 100
    seed_handles: list[str] = field(default_factory=list)
    fixture_path: Path | None = None


@dataclass(frozen=True)
class CollectionRunResult:
    """Collection run outcome emitted by CollectionAgent."""

    run_id: str
    status: Literal["completed", "partial", "failed"]
    artifacts_collected: int
    started_at: datetime
    finished_at: datetime
    error_message: str | None = None
    artifacts_skipped_unchanged: int = 0
