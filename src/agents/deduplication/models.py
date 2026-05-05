"""Data models for Phase 3 deduplication."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Literal


@dataclass(frozen=True)
class DedupThresholds:
    """Thresholds used for pair decisions."""

    fuzzy_merge: float
    embedding_merge: float
    fuzzy_review: float


@dataclass(frozen=True)
class DedupMention:
    """One mention candidate participating in dedup."""

    mention_id: str
    artifact_id: str
    source: Literal["entity", "relation_subject", "relation_object"]
    entity_type: str
    surface_form: str
    normalized: str


@dataclass(frozen=True)
class DedupPairScore:
    """Scored pair decision for auditability."""

    mention_id_a: str
    mention_id_b: str
    surface_a: str
    surface_b: str
    fuzzy_score: float
    embedding_score: float | None
    merged: bool
    rationale: Literal["fuzzy_only", "embedding_confirmed", "human_review", "rejected"]


@dataclass(frozen=True)
class DedupCluster:
    """Merged cluster output with canonical identity."""

    canonical_id: str
    canonical_surface: str
    aliases: list[str]
    mention_ids: list[str]


@dataclass(frozen=True)
class DedupAuditEntry:
    """Append-only decision event."""

    timestamp: datetime
    mention_id_a: str
    mention_id_b: str
    action: Literal["merged", "review", "rejected"]
    rationale: str
    fuzzy_score: float
    embedding_score: float | None


@dataclass(frozen=True)
class DedupReport:
    """Deterministic report for one run_id."""

    run_id: str
    embedding_backend: str
    thresholds_used: DedupThresholds
    mention_count: int
    clusters: list[DedupCluster] = field(default_factory=list)
    pair_scores: list[DedupPairScore] = field(default_factory=list)
    audit_log: list[DedupAuditEntry] = field(default_factory=list)


@dataclass(frozen=True)
class DedupRunResult:
    """Dedup run status summary."""

    run_id: str
    status: str
    clusters_written: int
    started_at: datetime
    finished_at: datetime
    embedding_backend: str
    error_message: str | None = None
