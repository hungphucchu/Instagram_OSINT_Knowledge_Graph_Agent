"""SQLite persistence for Phase 2 extraction outputs."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from schemas.extraction_record import ExtractionRecord


class ExtractionStore:
    """Stores and queries extraction records by run_id/artifact_id."""

    def __init__(self, db_path: Path) -> None:
        self._db_path = Path(db_path)
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    def upsert_many(self, records: list[ExtractionRecord]) -> int:
        if not records:
            return 0
        rows = [self._to_row(x) for x in records]
        with sqlite3.connect(self._db_path) as conn:
            conn.executemany(
                """
                INSERT INTO extraction_records (
                    artifact_id, run_id, extractor_model_id, mode, entities_json, relations_json
                ) VALUES (
                    :artifact_id, :run_id, :extractor_model_id, :mode, :entities_json, :relations_json
                )
                ON CONFLICT(artifact_id) DO UPDATE SET
                    run_id=excluded.run_id,
                    extractor_model_id=excluded.extractor_model_id,
                    mode=excluded.mode,
                    entities_json=excluded.entities_json,
                    relations_json=excluded.relations_json
                """,
                rows,
            )
            conn.commit()
        return len(rows)

    def list_by_run(self, run_id: str) -> list[ExtractionRecord]:
        with sqlite3.connect(self._db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT * FROM extraction_records WHERE run_id = ? ORDER BY artifact_id ASC",
                (run_id,),
            ).fetchall()
        return [self._from_row(dict(r)) for r in rows]

    def _init_schema(self) -> None:
        with sqlite3.connect(self._db_path) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS extraction_records (
                    artifact_id TEXT PRIMARY KEY,
                    run_id TEXT NOT NULL,
                    extractor_model_id TEXT NOT NULL,
                    mode TEXT NOT NULL,
                    entities_json TEXT NOT NULL,
                    relations_json TEXT NOT NULL
                )
                """
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_extraction_records_run_id ON extraction_records(run_id)"
            )
            conn.commit()

    @staticmethod
    def _to_row(record: ExtractionRecord) -> dict[str, str]:
        return {
            "artifact_id": record.artifact_id,
            "run_id": record.run_id,
            "extractor_model_id": record.extractor_model_id,
            "mode": record.mode,
            "entities_json": json.dumps(
                [e.model_dump() for e in record.entities], separators=(",", ":")
            ),
            "relations_json": json.dumps(
                [r.model_dump() for r in record.relations], separators=(",", ":")
            ),
        }

    @staticmethod
    def _from_row(row: dict[str, str]) -> ExtractionRecord:
        return ExtractionRecord.model_validate(
            {
                "artifact_id": row["artifact_id"],
                "run_id": row["run_id"],
                "extractor_model_id": row["extractor_model_id"],
                "mode": row["mode"],
                "entities": json.loads(row["entities_json"]),
                "relations": json.loads(row["relations_json"]),
            }
        )
