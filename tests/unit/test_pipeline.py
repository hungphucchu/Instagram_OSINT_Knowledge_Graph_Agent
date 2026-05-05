"""Unit tests for ``src/myproject/pipeline.py``."""

from __future__ import annotations

from pathlib import Path

import myproject.pipeline as pipeline_mod
import pytest


def test_pipeline_module_imports() -> None:
    import myproject.pipeline  # noqa: F401


def test_fixture_path_resolves_to_repo_root() -> None:
    path = pipeline_mod._fixture_path()
    assert path.name == "raw_artifacts.json"
    assert path.exists(), f"expected fixture at {path}"


def test_run_sample_ingest_returns_expected_shape(tmp_path: Path) -> None:
    summary = pipeline_mod.run_sample_ingest()
    assert set(summary) >= {"run_id", "raw_artifacts", "extraction_records", "dedup_clusters"}
    assert summary["raw_artifacts"] >= 1
    assert summary["extraction_records"] >= 1
    assert summary["dedup_clusters"] >= 0


def test_main_requires_sample_flag(monkeypatch: pytest.MonkeyPatch) -> None:
    with pytest.raises(SystemExit):
        pipeline_mod.main([])
