"""Deterministic quality checks over Neo4j + minimal SQLite cross-checks."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Protocol

from agents.collection.raw_artifact_store import RawArtifactStore
from agents.extraction.extraction_store import ExtractionStore
from schemas.quality_report import QualityViolation

_MAX_SAMPLE_IDS = 50
_ORPHAN_CRITICAL_THRESHOLD = 100


class GraphReadStore(Protocol):
    def run_read(self, query: str, params: dict[str, Any] | None = None) -> list[dict[str, Any]]: ...


def evaluate_deterministic(
    *,
    run_id: str,
    graph_store: GraphReadStore,
    raw_store: RawArtifactStore,
    extraction_store: ExtractionStore,
) -> list[QualityViolation]:
    violations: list[QualityViolation] = []

    # 1) Missing provenance: every node/edge for the run should carry source_run_id.
    missing_node_prov = graph_store.run_read(
        """
        MATCH (n)
        WHERE n.source_run_id = $run_id OR n.source_run_id IS NULL OR trim(toString(n.source_run_id)) = ''
        WITH n
        WHERE n.source_run_id IS NULL OR trim(toString(n.source_run_id)) = ''
        RETURN coalesce(n.node_id, '') AS id
        LIMIT 50
        """,
        {"run_id": run_id},
    )
    if missing_node_prov:
        violations.append(
            QualityViolation(
                rule_id="missing_node_provenance",
                severity="critical",
                message="Graph nodes missing source_run_id provenance",
                sample_ids=[str(r.get("id") or "") for r in missing_node_prov if str(r.get("id") or "")],
            )
        )

    missing_rel_prov = graph_store.run_read(
        """
        MATCH ()-[r]->()
        WHERE r.source_run_id = $run_id OR r.source_run_id IS NULL OR trim(toString(r.source_run_id)) = ''
        WITH r
        WHERE r.source_run_id IS NULL OR trim(toString(r.source_run_id)) = ''
        RETURN coalesce(r.rel_id, '') AS id
        LIMIT 50
        """,
        {"run_id": run_id},
    )
    if missing_rel_prov:
        violations.append(
            QualityViolation(
                rule_id="missing_relationship_provenance",
                severity="critical",
                message="Graph relationships missing source_run_id provenance",
                sample_ids=[str(r.get("id") or "") for r in missing_rel_prov if str(r.get("id") or "")],
            )
        )

    # 2) Duplicate/conflicting edges for same endpoints + type within run.
    # `MENTIONS` duplicates are common across repeated extraction evidence and are
    # treated as warnings unless they explode in volume.
    duplicate_edges = graph_store.run_read(
        """
        MATCH (a)-[r]->(b)
        WHERE r.source_run_id = $run_id
        WITH a.node_id AS from_id, b.node_id AS to_id, type(r) AS rel_type, count(*) AS c
        WHERE c > 1
        RETURN from_id, to_id, rel_type, c
        LIMIT 50
        """,
        {"run_id": run_id},
    )
    if duplicate_edges:
        critical_dups = [r for r in duplicate_edges if str(r.get("rel_type") or "") != "MENTIONS"]
        warning_dups = [r for r in duplicate_edges if str(r.get("rel_type") or "") == "MENTIONS"]
        if critical_dups:
            violations.append(
                QualityViolation(
                    rule_id="duplicate_conflicting_edges",
                    severity="critical",
                    message="Duplicate/conflicting non-MENTIONS edges share same endpoints and type",
                    sample_ids=[
                        f"{r.get('from_id','')}->{r.get('to_id','')}:{r.get('rel_type','')}"
                        for r in critical_dups[:_MAX_SAMPLE_IDS]
                    ],
                    metadata={"count": len(critical_dups)},
                )
            )
        if warning_dups:
            violations.append(
                QualityViolation(
                    rule_id="duplicate_mentions_edges",
                    severity="warning",
                    message="Duplicate MENTIONS edges detected (often noisy but non-fatal)",
                    sample_ids=[
                        f"{r.get('from_id','')}->{r.get('to_id','')}:{r.get('rel_type','')}"
                        for r in warning_dups[:_MAX_SAMPLE_IDS]
                    ],
                    metadata={"count": len(warning_dups)},
                )
            )

    # 3) Orphan nodes in this run slice.
    orphan_nodes = graph_store.run_read(
        """
        MATCH (n)
        WHERE n.source_run_id = $run_id
        AND NOT (n)--()
        RETURN coalesce(n.node_id, '') AS id
        LIMIT 50
        """,
        {"run_id": run_id},
    )
    if orphan_nodes:
        severity = "critical" if len(orphan_nodes) >= _ORPHAN_CRITICAL_THRESHOLD else "warning"
        violations.append(
            QualityViolation(
                rule_id="orphan_nodes",
                severity=severity,
                message="Nodes in run slice have no incident relationships",
                sample_ids=[str(r.get("id") or "") for r in orphan_nodes if str(r.get("id") or "")][:_MAX_SAMPLE_IDS],
                metadata={"count": len(orphan_nodes), "critical_threshold": _ORPHAN_CRITICAL_THRESHOLD},
            )
        )

    # 4) Invalid timestamps (Post.collected_at parseability).
    bad_times = graph_store.run_read(
        """
        MATCH (n:Post)
        WHERE n.source_run_id = $run_id
        RETURN coalesce(n.node_id, '' ) AS id, coalesce(n.collected_at, '') AS collected_at
        LIMIT 500
        """,
        {"run_id": run_id},
    )
    invalid_ids: list[str] = []
    for row in bad_times:
        raw = str(row.get("collected_at") or "").strip()
        if not raw:
            invalid_ids.append(str(row.get("id") or ""))
            continue
        try:
            datetime.fromisoformat(raw.replace("Z", "+00:00"))
        except Exception:
            invalid_ids.append(str(row.get("id") or ""))
    if invalid_ids:
        violations.append(
            QualityViolation(
                rule_id="invalid_post_timestamps",
                severity="critical",
                message="Post.collected_at is missing or invalid ISO timestamp",
                sample_ids=[x for x in invalid_ids if x][:_MAX_SAMPLE_IDS],
            )
        )

    # 5) Minimal SQLite cross-check: extraction rows should map to raw artifacts.
    raw_ids = {a.artifact_id for a in raw_store.list_by_run(run_id)}
    ext_ids = {x.artifact_id for x in extraction_store.list_by_run(run_id)}
    missing_raw = sorted(ext_ids - raw_ids)
    if missing_raw:
        violations.append(
            QualityViolation(
                rule_id="sqlite_extraction_missing_raw_artifact",
                severity="critical",
                message="Extraction rows reference artifact_id not present in raw_artifacts",
                sample_ids=missing_raw[:_MAX_SAMPLE_IDS],
                metadata={"missing_count": len(missing_raw)},
            )
        )

    return violations

