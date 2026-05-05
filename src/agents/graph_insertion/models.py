"""Data models for Phase 4 graph insertion."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class GraphInsertionRunResult:
    """Graph insertion run status summary."""

    run_id: str
    status: str
    nodes_created: int
    nodes_updated: int
    relationships_created: int
    relationships_updated: int
    started_at: datetime
    finished_at: datetime
    backend: str
    error_message: str | None = None
