"""CollectionAgent orchestrates adapter fetch + artifact persistence."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Literal

from schemas.raw_artifact import RawArtifact

from agents.collection.content_fingerprint import raw_post_fingerprint, stable_artifact_id
from agents.collection.models import CollectionRunConfig, CollectionRunResult
from agents.collection.raw_artifact_store import RawArtifactStore
from agents.collection.source_adapter import SourceAdapter


class CollectionAgent:
    """Executes one collection run and stores artifacts with run status."""

    def __init__(self, adapter: SourceAdapter, store: RawArtifactStore) -> None:
        self._adapter = adapter
        self._store = store

    def run(self, config: CollectionRunConfig) -> CollectionRunResult:
        started_at = datetime.now(UTC)
        skipped_unchanged = 0
        try:
            fetched = self._adapter.fetch(config=config)
            to_persist: list[RawArtifact] = []
            for a in fetched:
                fp = raw_post_fingerprint(a)
                latest = self._store.get_latest_by_platform_post_id(a.platform_post_id)
                if latest is not None and raw_post_fingerprint(latest) == fp:
                    skipped_unchanged += 1
                    continue
                aid = stable_artifact_id(a, fp)
                to_persist.append(
                    a.model_copy(
                        update={
                            "artifact_id": aid,
                            "run_id": config.run_id,
                            "collector_version": config.collector_version,
                        }
                    )
                )
            persisted_count = self._store.upsert_many(to_persist)
            status = self._resolve_status(
                fetched_len=len(fetched),
                persisted_count=persisted_count,
                skipped_unchanged=skipped_unchanged,
            )
            error_message: str | None = None
        except Exception as exc:
            persisted_count = 0
            skipped_unchanged = 0
            status = "failed"
            error_message = str(exc)

        finished_at = datetime.now(UTC)
        return CollectionRunResult(
            run_id=config.run_id,
            status=status,
            artifacts_collected=persisted_count,
            started_at=started_at,
            finished_at=finished_at,
            error_message=error_message,
            artifacts_skipped_unchanged=skipped_unchanged,
        )

    @staticmethod
    def _resolve_status(
        *,
        fetched_len: int,
        persisted_count: int,
        skipped_unchanged: int,
    ) -> Literal["completed", "partial"]:
        if fetched_len == 0:
            return "partial"
        if persisted_count > 0:
            return "completed"
        if skipped_unchanged == fetched_len:
            return "completed"
        return "partial"
