"""Provenance contract aligned with architecture §4.3 (Phase 0 schema only)."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from schemas.raw_artifact import RawArtifact


class ProvenanceV1(BaseModel):
    """Fields attached to persisted facts as the pipeline matures."""

    model_config = ConfigDict(extra="forbid")

    source_run_id: str = Field(description="Pipeline run UUID")
    collector_version: str = Field(description="Collection code or adapter version")
    extractor_model: str | None = Field(
        default=None,
        description="NER/RE model id when extraction has run",
    )
    snippet_hash: str | None = Field(
        default=None,
        description="Hash of supporting text span when available",
    )
    created_at: datetime | None = Field(
        default=None,
        description="Creation time of the upstream record when applicable",
    )
    ingested_at: datetime | None = Field(
        default=None,
        description="Time the fact entered the graph or warehouse",
    )


def provenance_from_raw_artifact(artifact: RawArtifact) -> ProvenanceV1:
    """Map a collected raw artifact onto the provenance envelope (Phase 0 helper)."""
    return ProvenanceV1(
        source_run_id=artifact.run_id,
        collector_version=artifact.collector_version,
        extractor_model=artifact.extractor_model,
        snippet_hash=artifact.snippet_hash,
        created_at=artifact.collected_at,
        ingested_at=artifact.ingested_at,
    )
