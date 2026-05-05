"""Phase 3 deduplication tests."""

from __future__ import annotations

from pathlib import Path

from agents.collection import (
    CollectionAgent,
    CollectionRunConfig,
    FixtureSourceAdapter,
    RawArtifactStore,
)
from agents.deduplication import DedupAgent, DedupStore
from agents.extraction import ExtractionAgent, ExtractionStore
from schemas.extraction_record import ExtractedEntity, ExtractedRelation, ExtractionRecord

REPO_ROOT = Path(__file__).resolve().parents[1]
FIXTURE_JSON = REPO_ROOT / "fixtures" / "raw_artifacts.json"


def test_phase3_dedup_from_phase2_records(tmp_path: Path) -> None:
    run_id = "66666666-6666-6666-6666-666666666666"
    raw_store = RawArtifactStore(db_path=tmp_path / "raw_artifacts.db")
    extraction_store = ExtractionStore(db_path=tmp_path / "extraction_records.db")
    dedup_store = DedupStore(db_path=tmp_path / "dedup_reports.db")

    collect_agent = CollectionAgent(
        adapter=FixtureSourceAdapter(fixture_path=FIXTURE_JSON),
        store=raw_store,
    )
    collect_result = collect_agent.run(
        CollectionRunConfig(
            run_id=run_id,
            collector_version="phase3-test",
            max_items=8,
        )
    )
    assert collect_result.status == "completed"

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

    dedup_agent = DedupAgent(
        extraction_store=extraction_store,
        dedup_store=dedup_store,
        embedding_backend="char_ngram",
        fuzzy_merge_threshold=0.90,
        embedding_merge_threshold=0.82,
        fuzzy_review_threshold=0.78,
        char_ngram_n=3,
    )
    result = dedup_agent.run(run_id=run_id)
    assert result.status == "completed"
    assert result.clusters_written >= 1

    report = dedup_store.get_by_run(run_id)
    assert report is not None
    assert report.run_id == run_id
    assert report.mention_count >= 1
    assert len(report.clusters) >= 1
    assert all(cluster.canonical_id.startswith("ent_") for cluster in report.clusters)


def test_phase3_dedup_merges_name_variants(tmp_path: Path) -> None:
    run_id = "77777777-7777-7777-7777-777777777777"
    extraction_store = ExtractionStore(db_path=tmp_path / "extraction_records.db")
    dedup_store = DedupStore(db_path=tmp_path / "dedup_reports.db")
    extraction_store.upsert_many(
        [
            ExtractionRecord(
                artifact_id="a1",
                run_id=run_id,
                extractor_model_id="heuristic:rules-v1",
                mode="heuristic",
                entities=[
                    ExtractedEntity(entity_type="ORG", surface_form="NASA", confidence=0.9),
                    ExtractedEntity(entity_type="ORG", surface_form="Nasa", confidence=0.8),
                ],
                relations=[
                    ExtractedRelation(
                        subject="NASA",
                        predicate="WORKS_AT",
                        object="Mission Control",
                        confidence=0.8,
                    )
                ],
            ),
            ExtractionRecord(
                artifact_id="a2",
                run_id=run_id,
                extractor_model_id="heuristic:rules-v1",
                mode="heuristic",
                entities=[
                    ExtractedEntity(entity_type="ORG", surface_form="@nasa", confidence=0.85),
                    ExtractedEntity(entity_type="ORG", surface_form="SpaceX", confidence=0.9),
                ],
                relations=[],
            ),
        ]
    )
    dedup_agent = DedupAgent(
        extraction_store=extraction_store,
        dedup_store=dedup_store,
        embedding_backend="char_ngram",
        fuzzy_merge_threshold=0.90,
        embedding_merge_threshold=0.82,
        fuzzy_review_threshold=0.78,
        char_ngram_n=3,
    )
    result = dedup_agent.run(run_id=run_id)
    assert result.status == "completed"

    report = dedup_store.get_by_run(run_id)
    assert report is not None
    nasa_clusters = [
        c
        for c in report.clusters
        if "NASA" in c.aliases or "@nasa" in c.aliases or "Nasa" in c.aliases
    ]
    assert len(nasa_clusters) == 1
    assert {"NASA", "Nasa", "@nasa"}.issubset(set(nasa_clusters[0].aliases))
    spacex_clusters = [c for c in report.clusters if "SpaceX" in c.aliases]
    assert len(spacex_clusters) == 1
    assert spacex_clusters[0].canonical_id != nasa_clusters[0].canonical_id
