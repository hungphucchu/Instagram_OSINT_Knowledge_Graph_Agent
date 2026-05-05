"""Phase 2 extraction baseline tests."""

from __future__ import annotations

from pathlib import Path

from agents.collection import (
    CollectionAgent,
    CollectionRunConfig,
    FixtureSourceAdapter,
    RawArtifactStore,
)
from agents.extraction import ExtractionAgent, ExtractionStore

REPO_ROOT = Path(__file__).resolve().parents[1]
FIXTURE_JSON = REPO_ROOT / "fixtures" / "raw_artifacts.json"


def test_phase2_extraction_from_fixture_collection(tmp_path: Path) -> None:
    run_id = "55555555-5555-5555-5555-555555555555"
    raw_store = RawArtifactStore(db_path=tmp_path / "raw_artifacts.db")
    extraction_store = ExtractionStore(db_path=tmp_path / "extraction_records.db")

    collect_agent = CollectionAgent(
        adapter=FixtureSourceAdapter(fixture_path=FIXTURE_JSON),
        store=raw_store,
    )
    collect_result = collect_agent.run(
        CollectionRunConfig(
            run_id=run_id,
            collector_version="phase2-test",
            max_items=10,
        )
    )
    assert collect_result.status == "completed"
    assert collect_result.artifacts_collected >= 1

    extract_agent = ExtractionAgent(
        raw_store=raw_store,
        extraction_store=extraction_store,
        mode="heuristic",
        llm_provider="openai",
        llm_model="gpt-4o-mini",
        llm_base_url="https://api.openai.com/v1",
        llm_api_key="",
        llm_timeout_seconds=30,
        max_concurrency=2,
    )
    extract_result = extract_agent.run(run_id=run_id)
    assert extract_result.status == "completed"
    assert extract_result.records_written >= 1

    rows = extraction_store.list_by_run(run_id)
    assert len(rows) >= 1
    assert all(x.run_id == run_id for x in rows)
    assert all(x.extractor_model_id == "heuristic:rules-v1" for x in rows)
    # At least one record should produce relation candidates from hashtags or mentions.
    assert any(len(r.relations) >= 1 for r in rows)
