"""LangGraph ingest: collect → extract → dedup → graph_insert → quality (Phase 5 loop)."""

from __future__ import annotations

from typing import Any, Literal

from langgraph.graph import END, START, StateGraph
from logging_context import new_run_id
from schemas.quality_report import QualityReport

from agents.collection.models import CollectionRunConfig, CollectionRunResult
from agents.deduplication.models import DedupRunResult
from agents.extraction.extraction_agent import ExtractionRunResult
from agents.graph_insertion.models import GraphInsertionRunResult
from agents.pipeline.runtime import PipelineRuntime
from agents.pipeline.state import PipelineInput, PipelineState


def _serialize_collection(r: CollectionRunResult) -> dict[str, Any]:
    return {
        "run_id": r.run_id,
        "status": r.status,
        "artifacts_collected": r.artifacts_collected,
        "artifacts_skipped_unchanged": r.artifacts_skipped_unchanged,
        "started_at": r.started_at.isoformat(),
        "finished_at": r.finished_at.isoformat(),
        "error_message": r.error_message,
    }


def _serialize_extraction(r: ExtractionRunResult) -> dict[str, Any]:
    return {
        "run_id": r.run_id,
        "status": r.status,
        "records_written": r.records_written,
        "started_at": r.started_at.isoformat(),
        "finished_at": r.finished_at.isoformat(),
        "mode": r.mode,
        "extractor_model_id": r.extractor_model_id,
        "error_message": r.error_message,
    }


def _serialize_dedup(r: DedupRunResult) -> dict[str, Any]:
    return {
        "run_id": r.run_id,
        "status": r.status,
        "clusters_written": r.clusters_written,
        "started_at": r.started_at.isoformat(),
        "finished_at": r.finished_at.isoformat(),
        "embedding_backend": r.embedding_backend,
        "error_message": r.error_message,
    }


def _serialize_graph_insert(r: GraphInsertionRunResult) -> dict[str, Any]:
    return {
        "run_id": r.run_id,
        "status": r.status,
        "nodes_created": r.nodes_created,
        "nodes_updated": r.nodes_updated,
        "relationships_created": r.relationships_created,
        "relationships_updated": r.relationships_updated,
        "started_at": r.started_at.isoformat(),
        "finished_at": r.finished_at.isoformat(),
        "backend": r.backend,
        "error_message": r.error_message,
    }


def _serialize_quality(report: QualityReport) -> dict[str, Any]:
    return {
        "run_id": report.run_id,
        "status": "passed" if report.gate_passed else "failed",
        "gate_passed": report.gate_passed,
        "rule_pack_version": report.rule_pack_version,
        "violations": [v.model_dump(mode="json") for v in report.violations],
        "report_path": report.report_path,
        "quarantine_path": report.quarantine_path,
        "evaluated_at": report.evaluated_at.isoformat(),
    }


def _route_post_collect(state: PipelineState) -> Literal["extract", "end"]:
    if state.get("skip_collect"):
        if not (state.get("run_id") or "").strip():
            return "end"
        return "extract"
    coll = state.get("collection") or {}
    if coll.get("status") == "failed":
        return "end"
    return "extract"


def _route_post_extract(state: PipelineState) -> Literal["dedup", "end"]:
    ex = state.get("extraction") or {}
    if ex.get("status") == "failed":
        return "end"
    return "dedup"


def _route_post_dedup(state: PipelineState) -> Literal["graph_insert", "end"]:
    d = state.get("dedup") or {}
    if d.get("status") == "failed":
        return "end"
    return "graph_insert"


def _route_post_graph_insert(state: PipelineState) -> Literal["quality", "end"]:
    gi = state.get("graph_insert") or {}
    if gi.get("status") != "completed" or gi.get("error_message"):
        return "end"
    return "quality"


def compile_linear_ingest_graph(runtime: PipelineRuntime) -> Any:
    """Build and compile the ingest `StateGraph` (Phase 5 quality gate + optional retry)."""
    max_quality_attempts = runtime.settings.quality_max_attempts
    retry_target = runtime.settings.quality_retry_target

    def _route_post_quality(state: PipelineState) -> Literal["end", "extract", "dedup"]:
        q = state.get("quality") or {}
        if q.get("status") == "error":
            return "end"
        if q.get("gate_passed"):
            return "end"
        attempt = int(state.get("quality_attempt") or 0)
        if attempt >= max_quality_attempts:
            return "end"
        return retry_target

    def collect(state: PipelineState) -> dict[str, Any]:
        if state.get("skip_collect"):
            rid = (state.get("run_id") or "").strip()
            return {"last_step": "collect_skipped", "run_id": rid}
        run_id = new_run_id()
        cfg = CollectionRunConfig(
            run_id=run_id,
            collector_version=state.get("collector_version") or "phase4-langgraph",
            max_items=int(state.get("max_items") or 50),
            seed_handles=list(state.get("seed_handles") or []),
        )
        result = runtime.collection_agent.run(cfg)
        return {
            "run_id": result.run_id,
            "last_step": "collect",
            "collection": _serialize_collection(result),
        }

    def extract(state: PipelineState) -> dict[str, Any]:
        run_id = (state.get("run_id") or "").strip()
        agent = runtime.extraction_agent()
        result = agent.run(run_id=run_id)
        return {"last_step": "extract", "extraction": _serialize_extraction(result)}

    def dedup(state: PipelineState) -> dict[str, Any]:
        run_id = (state.get("run_id") or "").strip()
        agent = runtime.dedup_agent()
        result = agent.run(run_id=run_id)
        return {"last_step": "dedup", "dedup": _serialize_dedup(result)}

    def graph_insert(state: PipelineState) -> dict[str, Any]:
        run_id = (state.get("run_id") or "").strip()
        agent = runtime.graph_insertion_agent()
        result = agent.run(run_id=run_id)
        return {"last_step": "graph_insert", "graph_insert": _serialize_graph_insert(result)}

    def quality(state: PipelineState) -> dict[str, Any]:
        run_id = (state.get("run_id") or "").strip()
        attempt = int(state.get("quality_attempt") or 0) + 1
        agent = runtime.quality_agent()
        try:
            report = agent.run(run_id=run_id)
        except Exception as exc:
            return {
                "last_step": "quality",
                "quality_attempt": attempt,
                "quality": {
                    "run_id": run_id,
                    "status": "error",
                    "gate_passed": False,
                    "error_message": str(exc),
                    "rule_pack_version": f"llm:{runtime.settings.quality_llm_provider}:{runtime.settings.quality_llm_model}",
                    "violations": [],
                    "report_path": None,
                    "quarantine_path": None,
                },
            }
        return {
            "last_step": "quality",
            "quality_attempt": attempt,
            "quality": _serialize_quality(report),
        }

    graph = StateGraph(PipelineState)
    graph.add_node("stage_collect", collect)
    graph.add_node("stage_extract", extract)
    graph.add_node("stage_dedup", dedup)
    graph.add_node("stage_graph_insert", graph_insert)
    graph.add_node("stage_quality", quality)
    graph.add_edge(START, "stage_collect")
    graph.add_conditional_edges(
        "stage_collect",
        _route_post_collect,
        {"extract": "stage_extract", "end": END},
    )
    graph.add_conditional_edges(
        "stage_extract",
        _route_post_extract,
        {"dedup": "stage_dedup", "end": END},
    )
    graph.add_conditional_edges(
        "stage_dedup",
        _route_post_dedup,
        {"graph_insert": "stage_graph_insert", "end": END},
    )
    graph.add_conditional_edges(
        "stage_graph_insert",
        _route_post_graph_insert,
        {"quality": "stage_quality", "end": END},
    )
    graph.add_conditional_edges(
        "stage_quality",
        _route_post_quality,
        {"end": END, "extract": "stage_extract", "dedup": "stage_dedup"},
    )
    return graph.compile()


def run_linear_pipeline(runtime: PipelineRuntime, inp: PipelineInput) -> PipelineState:
    """Execute ingest through the quality gate; returns final merged state."""
    app = compile_linear_ingest_graph(runtime)
    initial: PipelineState = {
        "skip_collect": inp.skip_collect,
        "run_id": (inp.run_id or "").strip(),
        "collector_version": inp.collector_version,
        "max_items": inp.max_items,
        "seed_handles": list(inp.seed_handles),
        "quality_attempt": 0,
    }
    return app.invoke(initial)  # type: ignore[no-any-return]


def pipeline_succeeded(final_state: PipelineState) -> bool:
    """True if quality gate passed and upstream stages produced usable work."""
    if final_state.get("last_step") != "quality":
        return False
    q = final_state.get("quality") or {}
    if q.get("status") == "error" or not q.get("gate_passed"):
        return False
    coll = final_state.get("collection") or {}
    ex = final_state.get("extraction") or {}
    collected = int(coll.get("artifacts_collected") or 0)
    skipped = int(coll.get("artifacts_skipped_unchanged") or 0)
    written = int(ex.get("records_written") or 0)
    if collected == 0 and skipped > 0 and written == 0:
        return False
    if collected > 0 and written == 0:
        return False
    gi = final_state.get("graph_insert") or {}
    return not (gi.get("status") != "completed" or gi.get("error_message"))
