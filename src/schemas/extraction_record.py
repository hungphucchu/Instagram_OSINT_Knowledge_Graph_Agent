"""Extraction output schema for Phase 2."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class ExtractedEntity(BaseModel):
    """One extracted entity mention from caption/bio text."""

    model_config = ConfigDict(extra="forbid")

    entity_type: str
    surface_form: str
    snippet: str | None = None
    start_offset: int | None = None
    end_offset: int | None = None
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)


class ExtractedRelation(BaseModel):
    """One extracted relation candidate between two entities."""

    model_config = ConfigDict(extra="forbid")

    subject: str
    predicate: str
    object: str
    evidence_span: str | None = None
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)


class ExtractionRecord(BaseModel):
    """Extraction result for one input artifact."""

    model_config = ConfigDict(extra="forbid")

    artifact_id: str
    run_id: str
    extractor_model_id: str
    mode: str
    entities: list[ExtractedEntity] = Field(default_factory=list)
    relations: list[ExtractedRelation] = Field(default_factory=list)
