"""ExtractionAgent orchestrates Phase 2 extraction over one run_id."""

from __future__ import annotations

import logging
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import UTC, datetime

from schemas.extraction_record import ExtractionRecord
from schemas.raw_artifact import RawArtifact

from agents.collection.raw_artifact_store import RawArtifactStore
from agents.extraction.extraction_store import ExtractionStore
from agents.extraction.heuristic_extractor import HeuristicExtractor
from agents.extraction.llm_extractor import LLMExtractor


@dataclass(frozen=True)
class ExtractionRunResult:
    """Extraction run status summary."""

    run_id: str
    status: str
    records_written: int
    started_at: datetime
    finished_at: datetime
    mode: str
    extractor_model_id: str
    error_message: str | None = None


class ExtractionAgent:
    """Runs extraction for all raw artifacts in a run_id."""

    def __init__(
        self,
        *,
        raw_store: RawArtifactStore,
        extraction_store: ExtractionStore,
        mode: str,
        llm_provider: str,
        llm_model: str,
        llm_base_url: str,
        llm_api_key: str,
        llm_timeout_seconds: int,
        max_concurrency: int,
    ) -> None:
        self._raw_store = raw_store
        self._extraction_store = extraction_store
        self._mode = mode
        self._heuristic = HeuristicExtractor()
        self._llm_provider = llm_provider
        self._llm_model = llm_model
        self._llm_base_url = llm_base_url
        self._llm_api_key = llm_api_key
        self._llm_timeout_seconds = llm_timeout_seconds
        self._max_concurrency = max(1, max_concurrency)
        self._log = logging.getLogger("extraction.agent")

    def run(self, *, run_id: str) -> ExtractionRunResult:
        started_at = datetime.now(UTC)
        try:
            artifacts = self._raw_store.list_by_run(run_id)
            records = self._extract_records_parallel(run_id=run_id, artifacts=artifacts)
            written = self._extraction_store.upsert_many(records)
            status = "completed" if written > 0 else "partial"
            error_message = None
        except Exception as exc:
            written = 0
            status = "failed"
            error_message = str(exc)

        finished_at = datetime.now(UTC)
        return ExtractionRunResult(
            run_id=run_id,
            status=status,
            records_written=written,
            started_at=started_at,
            finished_at=finished_at,
            mode=self._mode,
            extractor_model_id=self._extractor_model_id(),
            error_message=error_message,
        )

    def _extract_for_artifact(self, artifact: RawArtifact):
        if self._mode == "llm":
            # Separate LLMExtractor instance per task avoids cross-thread state issues.
            llm = LLMExtractor(
                provider=self._llm_provider,
                model_id=self._llm_model,
                base_url=self._llm_base_url,
                api_key=self._llm_api_key,
                timeout_seconds=self._llm_timeout_seconds,
                fallback=self._heuristic,
            )
            return llm.extract(artifact)
        if self._mode == "heuristic":
            return self._heuristic.extract(artifact)
        # Unknown mode falls back to heuristic to keep runs safe.
        return self._heuristic.extract(artifact)

    def _extractor_model_id(self) -> str:
        if self._mode == "llm":
            return f"{self._llm_provider}:{self._llm_model}"
        return "heuristic:rules-v1"

    def _extract_records_parallel(
        self, *, run_id: str, artifacts: list[RawArtifact]
    ) -> list[ExtractionRecord]:
        if not artifacts:
            return []
        records: list[ExtractionRecord] = []
        with ThreadPoolExecutor(max_workers=self._max_concurrency) as executor:
            futures = {
                executor.submit(self._extract_one_record, run_id, artifact): artifact.artifact_id
                for artifact in artifacts
            }
            for future in as_completed(futures):
                records.append(future.result())
        return records

    def _extract_one_record(self, run_id: str, artifact: RawArtifact) -> ExtractionRecord:
        item_started = time.monotonic()
        self._log.info(
            "extract_artifact_start run_id=%s artifact_id=%s mode=%s",
            run_id,
            artifact.artifact_id,
            self._mode,
        )
        entities, relations = self._extract_for_artifact(artifact)
        elapsed_ms = int((time.monotonic() - item_started) * 1000)
        self._log.info(
            "extract_artifact_done run_id=%s artifact_id=%s entities=%s relations=%s elapsed_ms=%s",
            run_id,
            artifact.artifact_id,
            len(entities),
            len(relations),
            elapsed_ms,
        )
        return ExtractionRecord(
            artifact_id=artifact.artifact_id,
            run_id=run_id,
            extractor_model_id=self._extractor_model_id(),
            mode=self._mode,
            entities=entities,
            relations=relations,
        )
