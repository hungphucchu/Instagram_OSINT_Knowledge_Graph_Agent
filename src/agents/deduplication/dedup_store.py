"""SQLite persistence for Phase 3 dedup reports and audit log."""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from pathlib import Path

from agents.deduplication.models import (
    DedupAuditEntry,
    DedupCluster,
    DedupPairScore,
    DedupReport,
    DedupThresholds,
)


class DedupStore:
    """Stores one dedup report per run_id."""

    def __init__(self, db_path: Path) -> None:
        self._db_path = Path(db_path)
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    def upsert_report(self, report: DedupReport) -> int:
        row = self._to_row(report)
        with sqlite3.connect(self._db_path) as conn:
            conn.execute(
                """
                INSERT INTO dedup_reports (
                    run_id,
                    embedding_backend,
                    mention_count,
                    thresholds_json,
                    clusters_json,
                    pair_scores_json,
                    audit_log_json
                ) VALUES (
                    :run_id,
                    :embedding_backend,
                    :mention_count,
                    :thresholds_json,
                    :clusters_json,
                    :pair_scores_json,
                    :audit_log_json
                )
                ON CONFLICT(run_id) DO UPDATE SET
                    embedding_backend=excluded.embedding_backend,
                    mention_count=excluded.mention_count,
                    thresholds_json=excluded.thresholds_json,
                    clusters_json=excluded.clusters_json,
                    pair_scores_json=excluded.pair_scores_json,
                    audit_log_json=excluded.audit_log_json
                """,
                row,
            )
            conn.commit()
        return len(report.clusters)

    def get_by_run(self, run_id: str) -> DedupReport | None:
        with sqlite3.connect(self._db_path) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                "SELECT * FROM dedup_reports WHERE run_id = ?",
                (run_id,),
            ).fetchone()
        if row is None:
            return None
        return self._from_row(dict(row))

    def _init_schema(self) -> None:
        with sqlite3.connect(self._db_path) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS dedup_reports (
                    run_id TEXT PRIMARY KEY,
                    embedding_backend TEXT NOT NULL,
                    mention_count INTEGER NOT NULL,
                    thresholds_json TEXT NOT NULL,
                    clusters_json TEXT NOT NULL,
                    pair_scores_json TEXT NOT NULL,
                    audit_log_json TEXT NOT NULL
                )
                """
            )
            conn.commit()

    @staticmethod
    def _to_row(report: DedupReport) -> dict[str, str | int]:
        return {
            "run_id": report.run_id,
            "embedding_backend": report.embedding_backend,
            "mention_count": report.mention_count,
            "thresholds_json": json.dumps(report.thresholds_used.__dict__, separators=(",", ":")),
            "clusters_json": json.dumps([x.__dict__ for x in report.clusters], separators=(",", ":")),
            "pair_scores_json": json.dumps([x.__dict__ for x in report.pair_scores], separators=(",", ":")),
            "audit_log_json": json.dumps(
                [
                    {
                        **x.__dict__,
                        "timestamp": x.timestamp.isoformat(),
                    }
                    for x in report.audit_log
                ],
                separators=(",", ":"),
            ),
        }

    @staticmethod
    def _from_row(row: dict[str, str | int]) -> DedupReport:
        thresholds_raw = json.loads(str(row["thresholds_json"]))
        clusters_raw = json.loads(str(row["clusters_json"]))
        pair_scores_raw = json.loads(str(row["pair_scores_json"]))
        audit_raw = json.loads(str(row["audit_log_json"]))
        return DedupReport(
            run_id=str(row["run_id"]),
            embedding_backend=str(row["embedding_backend"]),
            mention_count=int(row["mention_count"]),
            thresholds_used=DedupThresholds(**thresholds_raw),
            clusters=[DedupCluster(**x) for x in clusters_raw],
            pair_scores=[DedupPairScore(**x) for x in pair_scores_raw],
            audit_log=[
                DedupAuditEntry(
                    **{
                        **x,
                        "timestamp": datetime.fromisoformat(x["timestamp"]),
                    }
                )
                for x in audit_raw
            ],
        )
