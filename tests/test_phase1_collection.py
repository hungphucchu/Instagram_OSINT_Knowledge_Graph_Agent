"""Phase 1 collection implementation tests."""

from __future__ import annotations

from pathlib import Path

from agents.collection import (
    ApifyDataSourceAdapter,
    CollectionAgent,
    CollectionRunConfig,
    FixtureSourceAdapter,
    RawArtifactStore,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
FIXTURE_JSON = REPO_ROOT / "fixtures" / "raw_artifacts.json"
APIFY_LIVE_FIXTURE_JSON = REPO_ROOT / "fixtures" / "live_feed_items.json"


def test_fixture_collection_agent_persists_artifacts(tmp_path: Path) -> None:
    adapter = FixtureSourceAdapter(fixture_path=FIXTURE_JSON)
    store = RawArtifactStore(db_path=tmp_path / "raw_artifacts.db")
    agent = CollectionAgent(adapter=adapter, store=store)
    config = CollectionRunConfig(
        run_id="22222222-2222-2222-2222-222222222222",
        collector_version="phase1-test",
        max_items=10,
    )

    result = agent.run(config)

    assert result.status == "completed"
    assert result.artifacts_collected == 2
    rows = store.list_by_run(config.run_id)
    assert len(rows) == 2
    assert all(x.run_id == config.run_id for x in rows)
    assert all(x.adapter_id == "fixture" for x in rows)


def test_fixture_collection_upsert_is_idempotent_for_same_run(tmp_path: Path) -> None:
    adapter = FixtureSourceAdapter(fixture_path=FIXTURE_JSON)
    store = RawArtifactStore(db_path=tmp_path / "raw_artifacts.db")
    agent = CollectionAgent(adapter=adapter, store=store)
    config = CollectionRunConfig(
        run_id="33333333-3333-3333-3333-333333333333",
        collector_version="phase1-test",
        max_items=10,
    )

    result_1 = agent.run(config)
    result_2 = agent.run(config)

    assert result_1.artifacts_collected == 2
    assert result_1.artifacts_skipped_unchanged == 0
    assert result_2.artifacts_collected == 0
    assert result_2.artifacts_skipped_unchanged == 2
    assert result_2.status == "completed"
    rows = store.list_by_run(config.run_id)
    assert len(rows) == 2


def test_apify_data_collection_agent_persists_artifacts(tmp_path: Path) -> None:
    adapter = ApifyDataSourceAdapter(dataset_path=APIFY_LIVE_FIXTURE_JSON)
    store = RawArtifactStore(db_path=tmp_path / "raw_artifacts.db")
    agent = CollectionAgent(adapter=adapter, store=store)
    config = CollectionRunConfig(
        run_id="44444444-4444-4444-4444-444444444444",
        collector_version="phase1-test",
        max_items=10,
    )

    result = agent.run(config)

    assert result.status == "completed"
    assert result.artifacts_collected >= 1
    rows = store.list_by_run(config.run_id)
    assert len(rows) >= 1
    assert all(x.run_id == config.run_id for x in rows)
    assert all(x.adapter_id == "apify_data" for x in rows)


def test_fixture_collection_max_items_zero_means_all_rows(tmp_path: Path) -> None:
    adapter = FixtureSourceAdapter(fixture_path=FIXTURE_JSON)
    store = RawArtifactStore(db_path=tmp_path / "raw_artifacts.db")
    agent = CollectionAgent(adapter=adapter, store=store)
    config = CollectionRunConfig(
        run_id="dddddddd-dddd-dddd-dddd-dddddddddddd",
        collector_version="phase1-test",
        max_items=0,
    )
    result = agent.run(config)
    assert result.status == "completed"
    assert result.artifacts_collected == 2
    assert len(store.list_by_run(config.run_id)) == 2


def test_fixture_collection_skips_unchanged_across_new_run_id(tmp_path: Path) -> None:
    adapter = FixtureSourceAdapter(fixture_path=FIXTURE_JSON)
    store = RawArtifactStore(db_path=tmp_path / "raw_artifacts.db")
    agent = CollectionAgent(adapter=adapter, store=store)
    r1 = CollectionRunConfig(
        run_id="aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
        collector_version="v1",
        max_items=10,
    )
    r2 = CollectionRunConfig(
        run_id="bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb",
        collector_version="v1",
        max_items=10,
    )
    first = agent.run(r1)
    second = agent.run(r2)
    assert first.artifacts_collected == 2
    assert second.artifacts_collected == 0
    assert second.artifacts_skipped_unchanged == 2
    assert len(store.list_by_run(r1.run_id)) == 2
    assert len(store.list_by_run(r2.run_id)) == 0
