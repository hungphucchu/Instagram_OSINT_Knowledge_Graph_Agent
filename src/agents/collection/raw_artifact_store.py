"""SQLite-backed RawArtifact persistence for Phase 1."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from schemas.raw_artifact import RawArtifact


class RawArtifactStore:
    """Persists and queries RawArtifact records by run_id/artifact_id."""

    def __init__(self, db_path: Path) -> None:
        self._db_path = Path(db_path)
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    def upsert_many(self, artifacts: list[RawArtifact]) -> int:
        if not artifacts:
            return 0
        rows = [self._to_row(a) for a in artifacts]
        with sqlite3.connect(self._db_path) as conn:
            conn.executemany(
                """
                INSERT INTO raw_artifacts (
                    artifact_id, source_url, platform_post_id, caption_text, collected_at,
                    run_id, collector_version, adapter_id, hashtags, mentions, raw_payload,
                    extractor_model, snippet_hash, ingested_at
                ) VALUES (
                    :artifact_id, :source_url, :platform_post_id, :caption_text, :collected_at,
                    :run_id, :collector_version, :adapter_id, :hashtags, :mentions, :raw_payload,
                    :extractor_model, :snippet_hash, :ingested_at
                )
                ON CONFLICT(artifact_id) DO UPDATE SET
                    source_url=excluded.source_url,
                    platform_post_id=excluded.platform_post_id,
                    caption_text=excluded.caption_text,
                    collected_at=excluded.collected_at,
                    run_id=excluded.run_id,
                    collector_version=excluded.collector_version,
                    adapter_id=excluded.adapter_id,
                    hashtags=excluded.hashtags,
                    mentions=excluded.mentions,
                    raw_payload=excluded.raw_payload,
                    extractor_model=excluded.extractor_model,
                    snippet_hash=excluded.snippet_hash,
                    ingested_at=excluded.ingested_at
                """,
                rows,
            )
            conn.commit()
        return len(rows)

    def list_by_run(self, run_id: str) -> list[RawArtifact]:
        with sqlite3.connect(self._db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT * FROM raw_artifacts WHERE run_id = ? ORDER BY collected_at ASC",
                (run_id,),
            ).fetchall()
        return [self._from_row(dict(r)) for r in rows]

    def get_by_artifact_id(self, artifact_id: str) -> RawArtifact | None:
        with sqlite3.connect(self._db_path) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                "SELECT * FROM raw_artifacts WHERE artifact_id = ?",
                (artifact_id,),
            ).fetchone()
        return self._from_row(dict(row)) if row else None

    def _init_schema(self) -> None:
        with sqlite3.connect(self._db_path) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS raw_artifacts (
                    artifact_id TEXT PRIMARY KEY,
                    source_url TEXT NOT NULL,
                    platform_post_id TEXT NOT NULL,
                    caption_text TEXT NOT NULL,
                    collected_at TEXT NOT NULL,
                    run_id TEXT NOT NULL,
                    collector_version TEXT NOT NULL,
                    adapter_id TEXT NOT NULL,
                    hashtags TEXT NOT NULL,
                    mentions TEXT NOT NULL,
                    raw_payload TEXT NOT NULL,
                    extractor_model TEXT,
                    snippet_hash TEXT,
                    ingested_at TEXT
                )
                """
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_raw_artifacts_run_id ON raw_artifacts(run_id)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_raw_artifacts_platform_post_id "
                "ON raw_artifacts(platform_post_id)"
            )
            conn.commit()

    def get_latest_by_platform_post_id(self, platform_post_id: str) -> RawArtifact | None:
        """Most recently collected row for this post (by `collected_at`, then `artifact_id`)."""
        with sqlite3.connect(self._db_path) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                """
                SELECT * FROM raw_artifacts
                WHERE platform_post_id = ?
                ORDER BY collected_at DESC, artifact_id DESC
                LIMIT 1
                """,
                (platform_post_id,),
            ).fetchone()
        return self._from_row(dict(row)) if row else None

    @staticmethod
    def _to_row(artifact: RawArtifact) -> dict[str, str | None]:
        return {
            "artifact_id": artifact.artifact_id,
            "source_url": artifact.source_url,
            "platform_post_id": artifact.platform_post_id,
            "caption_text": artifact.caption_text,
            "collected_at": artifact.collected_at.isoformat(),
            "run_id": artifact.run_id,
            "collector_version": artifact.collector_version,
            "adapter_id": artifact.adapter_id,
            "hashtags": json.dumps(artifact.hashtags, separators=(",", ":")),
            "mentions": json.dumps(artifact.mentions, separators=(",", ":")),
            "raw_payload": json.dumps(artifact.raw_payload, separators=(",", ":")),
            "extractor_model": artifact.extractor_model,
            "snippet_hash": artifact.snippet_hash,
            "ingested_at": artifact.ingested_at.isoformat() if artifact.ingested_at else None,
        }

    @staticmethod
    def _from_row(row: dict[str, str | None]) -> RawArtifact:
        return RawArtifact.model_validate(
            {
                "artifact_id": row["artifact_id"],
                "source_url": row["source_url"],
                "platform_post_id": row["platform_post_id"],
                "caption_text": row["caption_text"],
                "collected_at": row["collected_at"],
                "run_id": row["run_id"],
                "collector_version": row["collector_version"],
                "adapter_id": row["adapter_id"],
                "hashtags": json.loads(row["hashtags"] or "[]"),
                "mentions": json.loads(row["mentions"] or "[]"),
                "raw_payload": json.loads(row["raw_payload"] or "{}"),
                "extractor_model": row["extractor_model"],
                "snippet_hash": row["snippet_hash"],
                "ingested_at": row["ingested_at"],
            }
        )
