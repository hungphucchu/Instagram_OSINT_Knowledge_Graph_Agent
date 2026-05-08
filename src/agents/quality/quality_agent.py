"""Phase 5 — LLM-only quality validation and report emission."""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from config import Settings
from schemas.quality_report import QualityReport, QualityViolation

from agents.collection.raw_artifact_store import RawArtifactStore
from agents.extraction.extraction_store import ExtractionStore
from agents.quality.deterministic_checks import evaluate_deterministic
from agents.quality.llm_judge import JudgeSample, QualityLLMJudge


class QualityAgent:
    """Runs LLM judge checks and writes QualityReport (+ optional quarantine list)."""

    def __init__(
        self,
        *,
        settings: Settings,
        graph_store: Any,
        raw_store: RawArtifactStore | None = None,
        extraction_store: ExtractionStore | None = None,
    ) -> None:
        self._settings = settings
        self._graph_store = graph_store
        self._raw_store = raw_store
        self._extraction_store = extraction_store
        self._log = logging.getLogger("quality.agent")
        self._llm_judge = QualityLLMJudge(
            provider=settings.quality_llm_provider,
            model_id=settings.quality_llm_model,
            base_url=settings.quality_llm_base_url,
            api_key=settings.quality_llm_api_key,
            timeout_seconds=settings.quality_llm_timeout_seconds,
            max_samples=settings.quality_llm_sample_size,
            max_concurrency=settings.quality_llm_max_concurrency,
            score_threshold=settings.quality_llm_min_score_threshold,
        )
        self._judge_version = f"llm:{settings.quality_llm_provider}:{settings.quality_llm_model}"

    def run(self, *, run_id: str) -> QualityReport:
        violations = self._evaluate_deterministic(run_id=run_id)
        violations.extend(self._evaluate_llm(run_id=run_id))
        critical = [v for v in violations if v.severity == "critical"]
        warn = [v for v in violations if v.severity == "warning"]
        fail_on_warn = self._settings.quality_fail_on_warning
        gate_passed = len(critical) == 0 and (not fail_on_warn or len(warn) == 0)

        evaluated_at = datetime.now(UTC)
        report_dir = Path(self._settings.quality_report_dir)
        report_dir.mkdir(parents=True, exist_ok=True)
        stamp = evaluated_at.strftime("%Y%m%dT%H%M%SZ")
        report_path = report_dir / f"quality_{run_id}_{stamp}.json"
        quarantine_path: Path | None = None

        report_model = QualityReport(
            run_id=run_id,
            rule_pack_version=self._judge_version,
            evaluated_at=evaluated_at,
            gate_passed=gate_passed,
            violations=violations,
            report_path=str(report_path),
            quarantine_path=None,
        )

        if critical:
            quarantine_path = report_dir / f"quarantine_{run_id}.json"
            q_payload = {
                "run_id": run_id,
                "created_at": evaluated_at.isoformat(),
                "reason": "critical_quality_violations",
                "rule_pack_version": self._judge_version,
                "sample_ids": sorted({sid for v in critical for sid in v.sample_ids if sid}),
                "violations": [v.model_dump() for v in critical],
            }
            quarantine_path.write_text(json.dumps(q_payload, indent=2), encoding="utf-8")
            report_model = report_model.model_copy(update={"quarantine_path": str(quarantine_path)})

        report_path.write_text(report_model.model_dump_json(indent=2), encoding="utf-8")
        self._log.info(
            "quality_run run_id=%s gate_passed=%s critical=%s warnings=%s report=%s",
            run_id,
            gate_passed,
            len(critical),
            len(warn),
            report_path,
        )
        return report_model

    def _evaluate_deterministic(self, *, run_id: str) -> list[QualityViolation]:
        if self._raw_store is None or self._extraction_store is None:
            self._log.warning("quality_deterministic_skipped reason=stores_missing")
            return []
        run_read = getattr(self._graph_store, "run_read", None)
        if not callable(run_read):
            self._log.warning("quality_deterministic_skipped reason=graph_read_unavailable")
            return []
        try:
            return evaluate_deterministic(
                run_id=run_id,
                graph_store=self._graph_store,
                raw_store=self._raw_store,
                extraction_store=self._extraction_store,
            )
        except Exception as exc:
            self._log.warning("quality_deterministic_error run_id=%s err=%s", run_id, exc)
            return []

    def _evaluate_llm(self, *, run_id: str) -> list[QualityViolation]:
        if not self._settings.quality_llm_enabled:
            self._log.info("quality_llm_skipped reason=disabled")
            return []
        if self._raw_store is None or self._extraction_store is None:
            self._log.warning("quality_llm_skipped reason=stores_missing")
            return []
        if not self._llm_judge.enabled:
            self._log.info("quality_llm_skipped reason=disabled_or_no_key")
            return []

        artifacts = {a.artifact_id: a for a in self._raw_store.list_by_run(run_id)}
        records = self._extraction_store.list_by_run(run_id)
        pairs: list[JudgeSample] = []
        for record in records:
            artifact = artifacts.get(record.artifact_id)
            if artifact is None:
                continue
            pairs.append(JudgeSample(artifact=artifact, extraction=record))
        return self._llm_judge.evaluate(pairs)
