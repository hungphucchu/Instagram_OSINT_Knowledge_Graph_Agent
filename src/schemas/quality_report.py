"""Structured output for Phase 5 QualityAgent."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class SuggestedFix(BaseModel):
    """Non-destructive remediation hint (informational only)."""

    model_config = ConfigDict(extra="forbid")

    action: str
    detail: str
    entity_ids: list[str] = Field(default_factory=list)


class QualityViolation(BaseModel):
    """One rule breach."""

    model_config = ConfigDict(extra="forbid")

    rule_id: str
    severity: Literal["critical", "warning"]
    message: str
    sample_ids: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
    suggested_fixes: list[SuggestedFix] = Field(default_factory=list)


class QualityReport(BaseModel):
    """Persisted quality gate result for a run."""

    model_config = ConfigDict(extra="forbid")

    run_id: str
    rule_pack_version: str
    evaluated_at: datetime
    gate_passed: bool
    violations: list[QualityViolation] = Field(default_factory=list)
    report_path: str | None = None
    quarantine_path: str | None = None
