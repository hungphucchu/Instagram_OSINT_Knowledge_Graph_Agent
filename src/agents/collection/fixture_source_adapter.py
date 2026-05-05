"""Fixture-backed SourceAdapter used in CI and local offline runs."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from agents.collection.fetch_limits import clamp_fetch_count
from agents.collection.models import CollectionRunConfig
from agents.collection.source_adapter import SourceAdapter
from schemas.raw_artifact import RawArtifact


class FixtureSourceAdapter(SourceAdapter):
    """Loads fixture rows and rebinds run-specific provenance fields."""

    def __init__(self, fixture_path: Path) -> None:
        self._fixture_path = Path(fixture_path)

    @property
    def adapter_id(self) -> str:
        return "fixture"

    def fetch(self, config: CollectionRunConfig) -> list[RawArtifact]:
        rows = json.loads(self._fixture_path.read_text(encoding="utf-8"))
        if not isinstance(rows, list):
            raise ValueError(f"Expected JSON array in fixture file: {self._fixture_path}")

        n = clamp_fetch_count(len(rows), config.max_items)
        artifacts: list[RawArtifact] = []
        for row in rows[:n]:
            artifacts.append(self._row_to_artifact(row=row, config=config))
        return artifacts

    def _row_to_artifact(self, *, row: dict[str, Any], config: CollectionRunConfig) -> RawArtifact:
        base = RawArtifact.model_validate(row)
        stable = hashlib.sha256(
            f"{base.platform_post_id}:{base.source_url}:{config.run_id}".encode("utf-8")
        ).hexdigest()[:24]
        return base.model_copy(
            update={
                "artifact_id": f"fixture-{stable}",
                "run_id": config.run_id,
                "collector_version": config.collector_version,
                "adapter_id": self.adapter_id,
            }
        )
