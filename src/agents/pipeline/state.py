"""Typed state for the ingest LangGraph (Phase 4 linear path)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, TypedDict


class PipelineState(TypedDict, total=False):
    """Merged state for collect → extract → dedup → graph_insert → quality."""

    run_id: str
    skip_collect: bool
    collector_version: str
    max_items: int
    seed_handles: list[str]
    last_step: str
    quality_attempt: int
    collection: dict[str, Any]
    extraction: dict[str, Any]
    dedup: dict[str, Any]
    graph_insert: dict[str, Any]
    quality: dict[str, Any]


@dataclass(frozen=True)
class PipelineInput:
    """CLI / API inputs for one pipeline invocation."""

    run_id: str | None = None
    collector_version: str = "phase4-langgraph-0.1.0"
    max_items: int = 50
    seed_handles: list[str] = field(default_factory=list)

    @property
    def skip_collect(self) -> bool:
        return self.run_id is not None and self.run_id != ""
