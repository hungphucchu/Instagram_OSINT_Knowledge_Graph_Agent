"""Phase 4 graph insertion tests."""

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
from agents.graph_insertion import GraphInsertionAgent

REPO_ROOT = Path(__file__).resolve().parents[1]
FIXTURE_JSON = REPO_ROOT / "fixtures" / "raw_artifacts.json"


class FakeGraphStore:
    def __init__(self) -> None:
        self.nodes: dict[str, tuple[str, dict]] = {}
        self.rels: dict[str, tuple[str, str, str, dict]] = {}
        self.constraints_ensured = False

    def ensure_constraints(self) -> None:
        self.constraints_ensured = True

    def upsert_node(
        self, *, node_id: str, label: str, properties: dict, source_run_id: str
    ) -> bool:
        created = node_id not in self.nodes
        self.nodes[node_id] = (label, {**properties, "source_run_id": source_run_id})
        return created

    def upsert_relationship(
        self,
        *,
        rel_id: str,
        rel_type: str,
        from_node_id: str,
        to_node_id: str,
        properties: dict,
        source_run_id: str,
    ) -> bool:
        created = rel_id not in self.rels
        self.rels[rel_id] = (
            rel_type,
            from_node_id,
            to_node_id,
            {**properties, "source_run_id": source_run_id},
        )
        return created

    def count_nodes(self) -> int:
        return len(self.nodes)

    def count_relationships(self) -> int:
        return len(self.rels)


def _prepare_phase1_to_phase3(
    tmp_path: Path, run_id: str
) -> tuple[RawArtifactStore, ExtractionStore, DedupStore]:
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
            collector_version="phase4-test",
            max_items=10,
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
    dedup_agent = DedupAgent(
        extraction_store=extraction_store,
        dedup_store=dedup_store,
        embedding_backend="char_ngram",
        fuzzy_merge_threshold=0.90,
        embedding_merge_threshold=0.82,
        fuzzy_review_threshold=0.78,
        char_ngram_n=3,
    )
    dedup_result = dedup_agent.run(run_id=run_id)
    assert dedup_result.status == "completed"
    return raw_store, extraction_store, dedup_store


def test_phase4_graph_insertion_idempotent(tmp_path: Path) -> None:
    run_id = "88888888-8888-8888-8888-888888888888"
    raw_store, extraction_store, dedup_store = _prepare_phase1_to_phase3(tmp_path, run_id)
    graph_store = FakeGraphStore()
    agent = GraphInsertionAgent(
        graph_backend="neo4j",
        graph_store=graph_store,
        raw_store=raw_store,
        extraction_store=extraction_store,
        dedup_store=dedup_store,
    )

    first = agent.run(run_id=run_id)
    assert first.status == "completed"
    assert first.nodes_created > 0
    assert first.relationships_created > 0
    canonical = [
        (nid, lab, props)
        for nid, (lab, props) in graph_store.nodes.items()
        if lab == "CanonicalEntity"
    ]
    assert canonical, "expected CanonicalEntity nodes from dedup"
    assert all("entity_kind" in props for _, _, props in canonical)
    nodes_after_first = graph_store.count_nodes()
    rels_after_first = graph_store.count_relationships()

    second = agent.run(run_id=run_id)
    assert second.status == "completed"
    assert second.nodes_created == 0
    assert second.relationships_created == 0
    assert second.nodes_updated >= 1
    assert second.relationships_updated >= 1
    assert graph_store.count_nodes() == nodes_after_first
    assert graph_store.count_relationships() == rels_after_first
    assert graph_store.constraints_ensured is True
