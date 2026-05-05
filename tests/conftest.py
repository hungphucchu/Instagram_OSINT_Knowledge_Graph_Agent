"""Shared pytest fixtures for the Instagram OSINT KG Agent test suite.

The default settings touch the local filesystem and (lazily) Neo4j. For unit
and integration tests we want a hermetic environment: pointing every store at
a temporary directory, disabling LLM calls, and never reaching out to a real
Neo4j instance.

Tests that *do* want a live LLM or live Neo4j set the relevant env vars
explicitly via monkeypatch (see ``tests/integration/test_query_pipeline.py``).
"""

from __future__ import annotations

from pathlib import Path

import pytest


@pytest.fixture(autouse=True)
def _isolated_env(
    tmp_path_factory: pytest.TempPathFactory, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Per-test isolated data dir and disabled LLM calls."""
    data_dir = tmp_path_factory.mktemp("kg-data")
    monkeypatch.setenv("DATA_DIR", str(data_dir))
    monkeypatch.setenv("COLLECTION_DB_PATH", str(data_dir / "raw_artifacts.db"))
    monkeypatch.setenv("EXTRACTION_DB_PATH", str(data_dir / "extraction_records.db"))
    monkeypatch.setenv("DEDUP_DB_PATH", str(data_dir / "dedup_reports.db"))
    monkeypatch.setenv("QUALITY_REPORT_DIR", str(data_dir / "reports"))
    monkeypatch.setenv("APIFY_CACHE_DIR", str(data_dir / "apify_cache"))

    # Default to the bundled fixture so collection in `apify_data` mode works
    # offline. Tests that need a different mode override this explicitly.
    monkeypatch.setenv("COLLECTION_MODE", "fixture")
    monkeypatch.setenv("COLLECTION_FIXTURE_PATH", str(_fixture_path()))

    # Heuristic extraction is offline; disable LLM by default.
    monkeypatch.setenv("EXTRACT_MODE", "heuristic")
    monkeypatch.setenv("EXTRACT_LLM_API_KEY", "")
    monkeypatch.setenv("QUALITY_LLM_ENABLED", "false")
    monkeypatch.setenv("QUALITY_LLM_API_KEY", "")
    monkeypatch.setenv("QUERY_LLM_ENABLED", "false")
    monkeypatch.setenv("QUERY_LLM_API_KEY", "")

    # Make sure each test sees a fresh Settings cache.
    from config import get_settings  # noqa: WPS433 (test-only import)

    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def _fixture_path() -> Path:
    here = Path(__file__).resolve().parents[1]
    return here / "fixtures" / "raw_artifacts.json"
