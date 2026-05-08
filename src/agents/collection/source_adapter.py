"""Adapter interface for Phase 1 collection sources."""

from __future__ import annotations

from abc import ABC, abstractmethod

from schemas.raw_artifact import RawArtifact

from agents.collection.models import CollectionRunConfig


class SourceAdapter(ABC):
    """Abstract source adapter API for collection stage."""

    @property
    @abstractmethod
    def adapter_id(self) -> str:
        """Stable identifier for adapter provenance."""

    @abstractmethod
    def fetch(self, config: CollectionRunConfig) -> list[RawArtifact]:
        """Fetch raw artifacts for one run."""
