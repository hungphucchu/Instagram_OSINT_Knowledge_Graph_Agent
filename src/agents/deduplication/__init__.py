"""Phase 3 deduplication package."""

from agents.deduplication.dedup_agent import DedupAgent
from agents.deduplication.dedup_store import DedupStore
from agents.deduplication.models import (
    DedupAuditEntry,
    DedupCluster,
    DedupMention,
    DedupPairScore,
    DedupReport,
    DedupRunResult,
    DedupThresholds,
)

__all__ = [
    "DedupAgent",
    "DedupStore",
    "DedupAuditEntry",
    "DedupCluster",
    "DedupMention",
    "DedupPairScore",
    "DedupReport",
    "DedupRunResult",
    "DedupThresholds",
]
