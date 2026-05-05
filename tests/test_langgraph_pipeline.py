"""Integration test: LangGraph linear ingest with fixtures (no Neo4j, no live Instagram)."""

from __future__ import annotations

from pathlib import Path

from agents.pipeline import (
    PipelineInput,
    PipelineRuntime,
    pipeline_succeeded,
    run_linear_pipeline,
)
from config import Settings

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


def test_langgraph_linear_pipeline_fixture(tmp_path: Path) -> None:
    settings = Settings(
        collection_db_path=tmp_path / "raw_artifacts.db",
        extraction_db_path=tmp_path / "extraction_records.db",
        dedup_db_path=tmp_path / "dedup_reports.db",
        quality_report_dir=tmp_path / "reports",
        collection_mode="fixture",
        collection_fixture_path=FIXTURE_JSON,
        extract_mode="heuristic",
    )
    fake = FakeGraphStore()
    runtime = PipelineRuntime.from_settings(settings, graph_store=fake)
    final = run_linear_pipeline(
        runtime,
        PipelineInput(max_items=10, collector_version="langgraph-test"),
    )
    assert pipeline_succeeded(final)
    assert fake.constraints_ensured is True
    assert fake.count_nodes() > 0
    assert fake.count_relationships() > 0
    assert (final.get("run_id") or "").strip() != ""


def test_langgraph_resume_skip_collect(tmp_path: Path) -> None:
    """collect once via pipeline, then resume from extract with --run-id."""
    settings = Settings(
        collection_db_path=tmp_path / "raw_artifacts.db",
        extraction_db_path=tmp_path / "extraction_records.db",
        dedup_db_path=tmp_path / "dedup_reports.db",
        quality_report_dir=tmp_path / "reports",
        collection_mode="fixture",
        collection_fixture_path=FIXTURE_JSON,
        extract_mode="heuristic",
    )
    fake = FakeGraphStore()
    runtime = PipelineRuntime.from_settings(settings, graph_store=fake)
    first = run_linear_pipeline(
        runtime,
        PipelineInput(max_items=10, collector_version="langgraph-test-resume-a"),
    )
    assert pipeline_succeeded(first)
    rid = (first.get("run_id") or "").strip()
    assert rid

    fake2 = FakeGraphStore()
    runtime2 = PipelineRuntime.from_settings(settings, graph_store=fake2)
    second = run_linear_pipeline(
        runtime2,
        PipelineInput(run_id=rid, collector_version="langgraph-test-resume-b"),
    )
    assert pipeline_succeeded(second)
    assert second.get("run_id") == rid
    assert fake2.count_nodes() > 0
