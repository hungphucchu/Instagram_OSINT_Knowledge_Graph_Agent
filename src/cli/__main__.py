"""CLI entrypoint — Phase 0 (validate fixtures, print config)."""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

from agents.collection import CollectionRunConfig, RawArtifactStore
from agents.collection.agent_factory import build_collection_agent
from agents.deduplication import DedupAgent, DedupStore
from agents.extraction import ExtractionAgent, ExtractionStore
from agents.graph_insertion import GraphInsertionAgent, Neo4jGraphStore
from agents.graph_insertion.neo4j_dev import wipe_all_graph_data
from agents.pipeline import PipelineInput, PipelineRuntime, pipeline_succeeded, run_linear_pipeline
from agents.query import QueryAgent, QueryRequest
from config import get_settings
from logging_context import new_run_id
from schemas.raw_artifact import RawArtifact

from cli.dev_reset import run_local_reset

__version__ = "0.1.0"


def _default_fixture_path() -> Path:
    return Path(__file__).resolve().parents[2] / "fixtures" / "raw_artifacts.json"


def cmd_validate_fixtures(path: Path, *, verbose: bool) -> int:
    log = logging.getLogger("cli")
    run_id = new_run_id()
    if verbose:
        logging.basicConfig(level=logging.INFO)
        log.info("run_id=%s validating %s", run_id, path)
    text = path.read_text(encoding="utf-8")
    rows = json.loads(text)
    if not isinstance(rows, list):
        log.error("run_id=%s expected JSON array in %s", run_id, path)
        return 1
    for i, item in enumerate(rows):
        RawArtifact.model_validate(item)
        if verbose:
            log.info("run_id=%s row=%s artifact_id=%s", run_id, i, item.get("artifact_id"))
    print(f"OK: validated {len(rows)} raw artifact(s) from {path}")
    return 0


def cmd_show_config(*, verbose: bool) -> int:
    s = get_settings()
    if verbose:
        logging.basicConfig(level=logging.INFO)
        logging.getLogger("cli").info("run_id=%s DATA_DIR=%s", new_run_id(), s.data_dir)
    print(f"data_dir={s.data_dir}")
    print(f"log_level={s.log_level}")
    print(f"collection_mode={s.collection_mode}")
    print(f"collection_fixture_path={s.collection_fixture_path}")
    print(f"collection_db_path={s.collection_db_path}")
    print(f"apify_data_path={s.apify_data_path}")
    print(f"apify_cache_dir={s.apify_cache_dir}")
    print(f"extract_mode={s.extract_mode}")
    print(f"extract_llm_provider={s.extract_llm_provider}")
    print(f"extract_llm_model={s.extract_llm_model}")
    print(f"extract_llm_base_url={s.extract_llm_base_url}")
    print(f"extract_llm_timeout_seconds={s.extract_llm_timeout_seconds}")
    print(f"extract_max_concurrency={s.extract_max_concurrency}")
    print(f"extraction_db_path={s.extraction_db_path}")
    print(f"dedup_db_path={s.dedup_db_path}")
    print(f"dedup_embedding_backend={s.dedup_embedding_backend}")
    print(f"dedup_fuzzy_merge_threshold={s.dedup_fuzzy_merge_threshold}")
    print(f"dedup_embedding_merge_threshold={s.dedup_embedding_merge_threshold}")
    print(f"dedup_fuzzy_review_threshold={s.dedup_fuzzy_review_threshold}")
    print(f"dedup_char_ngram_n={s.dedup_char_ngram_n}")
    print(f"graph_backend={s.graph_backend}")
    print(f"neo4j_uri={s.neo4j_uri}")
    print(f"neo4j_user={s.neo4j_user}")
    print(f"neo4j_database={s.neo4j_database}")
    print(f"query_llm_enabled={s.query_llm_enabled}")
    print(f"query_llm_provider={s.query_llm_provider}")
    print(f"query_llm_model={s.query_llm_model}")
    print(f"query_llm_base_url={s.query_llm_base_url}")
    print(f"query_max_limit={s.query_max_limit}")
    print(f"query_max_evidence_rows={s.query_max_evidence_rows}")
    return 0


def cmd_collect(*, max_items: int | None, usernames: list[str], verbose: bool) -> int:
    s = get_settings()
    run_id = new_run_id()
    normalized_usernames = [h.strip().lstrip("@") for h in usernames if h.strip()]
    cfg = CollectionRunConfig(
        run_id=run_id,
        collector_version="phase1-0.1.0",
        max_items=max_items or s.apify_max_items_per_run,
        seed_handles=normalized_usernames,
    )
    if s.collection_mode == "apify" and not cfg.seed_handles:
        print(
            "error: COLLECTION_MODE=apify requires at least one --username (e.g. --username nasa)",
            file=sys.stderr,
        )
        return 1
    if verbose:
        logging.basicConfig(level=logging.INFO)
        logging.getLogger("cli").info(
            "run_id=%s collection_mode=%s max_items=%s seed_handles=%s",
            run_id,
            s.collection_mode,
            cfg.max_items,
            ",".join(cfg.seed_handles) or "-",
        )
    agent = build_collection_agent(s)
    result = agent.run(cfg)
    rows_for_run: list[RawArtifact] = []
    if verbose:
        store = RawArtifactStore(db_path=s.collection_db_path)
        rows_for_run = store.list_by_run(run_id=result.run_id)
    print(
        f"run_id={result.run_id} status={result.status} artifacts_collected={result.artifacts_collected} "
        f"artifacts_skipped_unchanged={result.artifacts_skipped_unchanged} started_at={result.started_at.isoformat()} finished_at={result.finished_at.isoformat()}"
    )
    if verbose:
        sample_ids = ", ".join(x.artifact_id for x in rows_for_run[:3]) or "-"
        print(f"collection_db_path={s.collection_db_path}")
        print(f"stored_rows_for_run={len(rows_for_run)}")
        print(f"sample_artifact_ids={sample_ids}")
    if result.error_message:
        print(f"error={result.error_message}", file=sys.stderr)
        return 1
    return 0


def cmd_extract(*, run_id: str, verbose: bool, show_relations: bool) -> int:
    s = get_settings()
    raw_store = RawArtifactStore(db_path=s.collection_db_path)
    extraction_store = ExtractionStore(db_path=s.extraction_db_path)
    agent = ExtractionAgent(
        raw_store=raw_store,
        extraction_store=extraction_store,
        mode=s.extract_mode,
        llm_provider=s.extract_llm_provider,
        llm_model=s.extract_llm_model,
        llm_base_url=s.extract_llm_base_url,
        llm_api_key=s.extract_llm_api_key,
        llm_timeout_seconds=s.extract_llm_timeout_seconds,
        max_concurrency=s.extract_max_concurrency,
    )
    if verbose:
        logging.basicConfig(level=logging.INFO)
        logging.getLogger("cli").info(
            "run_id=%s extract_mode=%s extractor=%s:%s",
            run_id,
            s.extract_mode,
            s.extract_llm_provider,
            s.extract_llm_model,
        )
    result = agent.run(run_id=run_id)
    print(
        f"run_id={result.run_id} status={result.status} records_written={result.records_written} mode={result.mode} extractor_model_id={result.extractor_model_id}"
    )
    if verbose:
        rows = extraction_store.list_by_run(run_id=result.run_id)
        sample = ", ".join(x.artifact_id for x in rows[:3]) or "-"
        print(f"extraction_db_path={s.extraction_db_path}")
        print(f"stored_rows_for_run={len(rows)}")
        print(f"sample_artifact_ids={sample}")
        if show_relations:
            printed = 0
            print("sample_relations:")
            for row in rows:
                for rel in row.relations:
                    print(
                        f"- artifact_id={row.artifact_id} "
                        f"{rel.subject} --{rel.predicate}--> {rel.object} "
                        f"(confidence={rel.confidence:.2f})"
                    )
                    printed += 1
                    if printed >= 15:
                        return 0 if not result.error_message else 1
            if printed == 0:
                print("- (no relations found)")
    if result.error_message:
        print(f"error={result.error_message}", file=sys.stderr)
        return 1
    return 0


def cmd_dedup(*, run_id: str, verbose: bool, show_pairs: bool) -> int:
    s = get_settings()
    extraction_store = ExtractionStore(db_path=s.extraction_db_path)
    dedup_store = DedupStore(db_path=s.dedup_db_path)
    agent = DedupAgent(
        extraction_store=extraction_store,
        dedup_store=dedup_store,
        embedding_backend=s.dedup_embedding_backend,
        fuzzy_merge_threshold=s.dedup_fuzzy_merge_threshold,
        embedding_merge_threshold=s.dedup_embedding_merge_threshold,
        fuzzy_review_threshold=s.dedup_fuzzy_review_threshold,
        char_ngram_n=s.dedup_char_ngram_n,
    )
    if verbose:
        logging.basicConfig(level=logging.INFO)
        logging.getLogger("cli").info(
            "run_id=%s dedup_backend=%s fuzzy_merge=%.2f embedding_merge=%.2f fuzzy_review=%.2f",
            run_id,
            s.dedup_embedding_backend,
            s.dedup_fuzzy_merge_threshold,
            s.dedup_embedding_merge_threshold,
            s.dedup_fuzzy_review_threshold,
        )
    result = agent.run(run_id=run_id)
    print(
        f"run_id={result.run_id} status={result.status} clusters_written={result.clusters_written} embedding_backend={result.embedding_backend}"
    )
    report = dedup_store.get_by_run(run_id=result.run_id)
    if verbose and report is not None:
        print(f"dedup_db_path={s.dedup_db_path}")
        print(f"mention_count={report.mention_count}")
        print(f"cluster_count={len(report.clusters)}")
        print(f"pair_scores_count={len(report.pair_scores)}")
        print(f"audit_log_count={len(report.audit_log)}")
        print("sample_clusters:")
        for cluster in report.clusters[:5]:
            print(
                f"- canonical_id={cluster.canonical_id} canonical_surface={cluster.canonical_surface} aliases={len(cluster.aliases)} mentions={len(cluster.mention_ids)}"
            )
        if not report.clusters:
            print("- (no clusters found)")
        if show_pairs:
            print("sample_pair_scores:")
            review_pairs = [x for x in report.pair_scores if x.rationale == "human_review"]
            merged_pairs = [x for x in report.pair_scores if x.merged]
            review_pairs.sort(key=lambda x: x.fuzzy_score, reverse=True)
            merged_pairs.sort(key=lambda x: (x.embedding_score or 0.0), reverse=True)
            printed = 0
            for pair in review_pairs[:8] + merged_pairs[:8]:
                print(
                    "- [{rationale}] {a} <-> {b} "
                    "fuzzy={fuzzy:.3f} embedding={embedding}".format(
                        rationale=pair.rationale,
                        a=pair.surface_a,
                        b=pair.surface_b,
                        fuzzy=pair.fuzzy_score,
                        embedding=f"{pair.embedding_score:.3f}"
                        if pair.embedding_score is not None
                        else "-",
                    )
                )
                printed += 1
                if printed >= 16:
                    break
            if printed == 0:
                print("- (no pair scores found)")
    if result.error_message:
        print(f"error={result.error_message}", file=sys.stderr)
        return 1
    return 0


def cmd_graph_insert(*, run_id: str, verbose: bool) -> int:
    s = get_settings()
    raw_store = RawArtifactStore(db_path=s.collection_db_path)
    extraction_store = ExtractionStore(db_path=s.extraction_db_path)
    dedup_store = DedupStore(db_path=s.dedup_db_path)
    graph_store = Neo4jGraphStore(
        uri=s.neo4j_uri,
        user=s.neo4j_user,
        password=s.neo4j_password,
        database=s.neo4j_database,
    )
    agent = GraphInsertionAgent(
        graph_backend=s.graph_backend,
        graph_store=graph_store,
        raw_store=raw_store,
        extraction_store=extraction_store,
        dedup_store=dedup_store,
    )
    if verbose:
        logging.basicConfig(level=logging.INFO)
        logging.getLogger("cli").info(
            "run_id=%s graph_backend=%s neo4j_uri=%s neo4j_database=%s",
            run_id,
            s.graph_backend,
            s.neo4j_uri,
            s.neo4j_database,
        )
    result = agent.run(run_id=run_id)
    print(
        f"run_id={result.run_id} status={result.status} backend={result.backend} "
        f"nodes_created={result.nodes_created} nodes_updated={result.nodes_updated} "
        f"relationships_created={result.relationships_created} relationships_updated={result.relationships_updated}"
    )
    if verbose:
        print(f"neo4j_uri={s.neo4j_uri}")
        print(f"neo4j_database={s.neo4j_database}")
        print(f"graph_nodes_total={graph_store.count_nodes()}")
        print(f"graph_relationships_total={graph_store.count_relationships()}")
    if result.error_message:
        print(f"error={result.error_message}", file=sys.stderr)
        return 1
    return 0


def cmd_graph_wipe(*, yes: bool, verbose: bool) -> int:
    """Dev only: delete all nodes and relationships in NEO4J_DATABASE."""
    if not yes:
        print(
            "error: graph-wipe is destructive; re-run with --yes "
            "(MATCH (n) DETACH DELETE n on your configured Neo4j database).",
            file=sys.stderr,
        )
        return 1
    s = get_settings()
    if s.graph_backend != "neo4j":
        print("error: graph-wipe only supports GRAPH_BACKEND=neo4j", file=sys.stderr)
        return 1
    if verbose:
        logging.basicConfig(level=logging.INFO)
        logging.getLogger("cli").info(
            "graph_wipe neo4j_uri=%s neo4j_database=%s",
            s.neo4j_uri,
            s.neo4j_database,
        )
    wipe_all_graph_data(
        uri=s.neo4j_uri,
        user=s.neo4j_user,
        password=s.neo4j_password,
        database=s.neo4j_database,
    )
    store = Neo4jGraphStore(
        uri=s.neo4j_uri,
        user=s.neo4j_user,
        password=s.neo4j_password,
        database=s.neo4j_database,
    )
    try:
        n = store.count_nodes()
        r = store.count_relationships()
    finally:
        store.close()
    print(f"graph_wipe_ok nodes_remaining={n} relationships_remaining={r}")
    if n != 0 or r != 0:
        print("warning: graph not fully empty; check permissions or DB name.", file=sys.stderr)
        return 1
    return 0


def cmd_local_reset(*, yes: bool, verbose: bool) -> int:
    """Dev: delete pipeline SQLite DBs (from Settings) and wipe Neo4j."""
    if not yes:
        print(
            "error: local-reset removes COLLECTION_DB_PATH, EXTRACTION_DB_PATH, DEDUP_DB_PATH "
            "and empties Neo4j; re-run with --yes.",
            file=sys.stderr,
        )
        return 1
    return run_local_reset(verbose=verbose)


def cmd_quality(*, run_id: str, verbose: bool) -> int:
    """Run Phase 5 quality gate once for a run_id (writes reports under QUALITY_REPORT_DIR)."""
    rid = run_id.strip()
    if not rid:
        print("error: --run-id is required", file=sys.stderr)
        return 1
    s = get_settings()
    if verbose:
        logging.basicConfig(level=logging.INFO)
        logging.getLogger("cli").info("quality run_id=%s judge=%s:%s", rid, s.quality_llm_provider, s.quality_llm_model)
    runtime = PipelineRuntime.from_settings(s)
    agent = runtime.quality_agent()
    report = agent.run(run_id=rid)
    print(
        f"quality gate_passed={report.gate_passed} violations={len(report.violations)} "
        f"report={report.report_path}"
    )
    if report.quarantine_path:
        print(f"quality quarantine={report.quarantine_path}")
    return 0 if report.gate_passed else 1


def cmd_pipeline(
    *,
    run_id: str | None,
    max_items: int | None,
    usernames: list[str],
    verbose: bool,
) -> int:
    """Run LangGraph ingest through Phase 5 quality gate."""
    s = get_settings()
    normalized = [h.strip().lstrip("@") for h in usernames if h.strip()]
    rid_in = (run_id or "").strip()
    inp = PipelineInput(
        run_id=rid_in if rid_in else None,
        collector_version="phase4-langgraph-0.1.0",
        max_items=max_items if max_items is not None else s.apify_max_items_per_run,
        seed_handles=normalized,
    )
    if inp.skip_collect and not (inp.run_id or "").strip():
        print(
            "error: --run-id is required when resuming (skipping collection) for the pipeline",
            file=sys.stderr,
        )
        return 1
    if s.collection_mode == "apify" and not inp.skip_collect and not inp.seed_handles:
        print(
            "error: COLLECTION_MODE=apify requires at least one --username for the pipeline",
            file=sys.stderr,
        )
        return 1
    if verbose:
        logging.basicConfig(level=logging.INFO)
        logging.getLogger("cli").info(
            "pipeline collection_mode=%s skip_collect=%s run_id=%s max_items=%s",
            s.collection_mode,
            inp.skip_collect,
            inp.run_id or "(new)",
            inp.max_items,
        )
    runtime = PipelineRuntime.from_settings(s)
    final = run_linear_pipeline(runtime, inp)
    run_final = (final.get("run_id") or "").strip() or "-"
    print(f"pipeline_run_id={run_final} last_step={final.get('last_step')}")
    coll = final.get("collection") or {}
    ex = final.get("extraction") or {}
    if isinstance(coll, dict):
        print(
            "  collection: artifacts_collected={c} artifacts_skipped_unchanged={s} status={st}".format(
                c=coll.get("artifacts_collected"),
                s=coll.get("artifacts_skipped_unchanged"),
                st=coll.get("status"),
            )
        )
    if isinstance(ex, dict):
        print(
            "  extraction: records_written={w} status={st}".format(
                w=ex.get("records_written"),
                st=ex.get("status"),
            )
        )
    for key in ("dedup", "graph_insert", "quality"):
        block = final.get(key)
        if isinstance(block, dict) and block:
            st = block.get("status")
            print(f"  {key}_status={st}")
    if not pipeline_succeeded(final):
        err_parts = []
        for key in ("collection", "extraction", "dedup", "graph_insert", "quality"):
            block = final.get(key)
            if isinstance(block, dict) and block.get("error_message"):
                err_parts.append(f"{key}={block.get('error_message')}")
        if err_parts:
            print("error=" + "; ".join(err_parts), file=sys.stderr)
        elif final.get("last_step") not in ("graph_insert", "quality"):
            print(
                f"error=pipeline stopped early (last_step={final.get('last_step')})",
                file=sys.stderr,
            )
        else:
            fc = final.get("collection") or {}
            fe = final.get("extraction") or {}
            if (
                int(fc.get("artifacts_collected") or 0) == 0
                and int(fc.get("artifacts_skipped_unchanged") or 0) > 0
                and int(fe.get("records_written") or 0) == 0
            ):
                print(
                    "error=all collected items were unchanged (skipped); this run_id has no new raw rows. "
                    "Use `pipeline --run-id <earlier_run_with_data>` to continue from an existing run, "
                    "or delete/reset raw_artifacts.db / change data so collection stores new rows.",
                    file=sys.stderr,
                )
            elif int(fc.get("artifacts_collected") or 0) > 0 and int(fe.get("records_written") or 0) == 0:
                print(
                    "error=collection stored artifacts but extraction wrote 0 records; "
                    "check EXTRACT_MODE / LLM settings and logs.",
                    file=sys.stderr,
                )
            else:
                gi = final.get("graph_insert") or {}
                q = final.get("quality") or {}
                if q.get("status") == "error" or (q and not q.get("gate_passed")):
                    print(
                        f"error=quality status={q.get('status')} gate_passed={q.get('gate_passed')} "
                        f"violations={len(q.get('violations') or [])} message={q.get('error_message')}",
                        file=sys.stderr,
                    )
                else:
                    print(
                        f"error=graph_insert status={gi.get('status')} "
                        f"message={gi.get('error_message')}",
                        file=sys.stderr,
                    )
        return 1
    gi = final.get("graph_insert") or {}
    qfin = final.get("quality") or {}
    print(
        "graph_insert nodes_created={nc} relationships_created={rc}".format(
            nc=gi.get("nodes_created"),
            rc=gi.get("relationships_created"),
        )
    )
    print(
        "quality gate_passed={gp} report={rp}".format(
            gp=qfin.get("gate_passed"),
            rp=qfin.get("report_path"),
        )
    )
    return 0


def cmd_query(*, question: str, verbose: bool, show_cypher: bool) -> int:
    q = question.strip()
    if not q:
        print("error: --question is required", file=sys.stderr)
        return 1
    s = get_settings()
    if verbose:
        logging.basicConfig(level=logging.INFO)
        logging.getLogger("cli").info("query provider=%s model=%s", s.query_llm_provider, s.query_llm_model)
    store = Neo4jGraphStore(uri=s.neo4j_uri, user=s.neo4j_user, password=s.neo4j_password, database=s.neo4j_database)
    agent = QueryAgent(settings=s, graph_store=store)
    resp = agent.answer(QueryRequest(question=q, include_cypher=show_cypher))
    print(f"query_id={resp.query_id}")
    print(f"answer={resp.answer}")
    print(f"evidence_rows={len(resp.evidence)}")
    print("evidence=" + json.dumps(resp.evidence, ensure_ascii=True))
    if show_cypher and resp.cypher:
        print(f"cypher={resp.cypher}")
    if resp.warnings:
        print("warnings=" + "; ".join(resp.warnings))
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="cli",
        description="Instagram OSINT KG — Phase 0 dev CLI (not the primary API surface)",
    )
    parser.add_argument("--version", action="store_true", help="print package version and exit")
    sub = parser.add_subparsers(dest="command", help="available commands")

    p_val = sub.add_parser("validate-fixtures", help="validate fixtures/raw_artifacts.json against RawArtifact")
    p_val.add_argument(
        "--path",
        type=Path,
        default=None,
        help="path to JSON array (default: repo fixtures/raw_artifacts.json)",
    )
    p_val.add_argument("-v", "--verbose", action="store_true")

    p_cfg = sub.add_parser("show-config", help="print resolved Settings (no secrets in Phase 0)")
    p_cfg.add_argument("-v", "--verbose", action="store_true")
    p_collect = sub.add_parser("collect", help="run Phase 1 collection with configured adapter")
    p_collect.add_argument(
        "--max-items",
        type=int,
        default=None,
        help="override APIFY_MAX_ITEMS_PER_RUN; 0 or negative = no cap (file-backed modes).",
    )
    p_collect.add_argument(
        "--username",
        action="append",
        default=[],
        help="Instagram username to collect from (repeatable). Required for COLLECTION_MODE=apify.",
    )
    p_collect.add_argument(
        "--seed-handle",
        action="append",
        default=[],
        help="Deprecated alias for --username.",
    )
    p_collect.add_argument("-v", "--verbose", action="store_true")
    p_extract = sub.add_parser("extract", help="run Phase 2 extraction for a run_id")
    p_extract.add_argument("--run-id", required=True, help="run_id to extract from raw store")
    p_extract.add_argument(
        "--show-relations",
        action="store_true",
        help="print a sample of extracted relations after storing results",
    )
    p_extract.add_argument("-v", "--verbose", action="store_true")
    p_dedup = sub.add_parser("dedup", help="run Phase 3 deduplication for a run_id")
    p_dedup.add_argument("--run-id", required=True, help="run_id to deduplicate from extraction store")
    p_dedup.add_argument(
        "--show-pairs",
        action="store_true",
        help="print sample pair scores (human_review + merged candidates)",
    )
    p_dedup.add_argument("-v", "--verbose", action="store_true")
    p_graph = sub.add_parser("graph-insert", help="run Phase 4 graph insertion for a run_id")
    p_graph.add_argument("--run-id", required=True, help="run_id to insert into graph backend")
    p_graph.add_argument("-v", "--verbose", action="store_true")
    p_quality = sub.add_parser("quality", help="run Phase 5 quality gate for a run_id (read-only graph)")
    p_quality.add_argument("--run-id", required=True, help="run_id whose graph slice to evaluate")
    p_quality.add_argument("-v", "--verbose", action="store_true")
    p_query = sub.add_parser("query", help="run Phase 6 QueryAgent (NL -> read-only Cypher -> answer)")
    p_query.add_argument("--question", required=True, help="natural-language question")
    p_query.add_argument("--show-cypher", action="store_true", help="print verified query for audit")
    p_query.add_argument("-v", "--verbose", action="store_true")
    p_wipe = sub.add_parser(
        "graph-wipe",
        help="dev only: delete ALL nodes and relationships in Neo4j (uses .env NEO4J_*)",
    )
    p_wipe.add_argument(
        "--yes",
        action="store_true",
        help="required; without it the command refuses to run",
    )
    p_wipe.add_argument("-v", "--verbose", action="store_true")
    p_reset = sub.add_parser(
        "local-reset",
        help="dev only: delete pipeline SQLite DBs + wipe Neo4j (uses .env paths and NEO4J_*)",
    )
    p_reset.add_argument(
        "--yes",
        action="store_true",
        help="required safeguard",
    )
    p_reset.add_argument("-v", "--verbose", action="store_true")
    p_pipe = sub.add_parser(
        "pipeline",
        help="LangGraph ingest: collect → extract → dedup → graph_insert → quality (Phase 5)",
    )
    p_pipe.add_argument(
        "--run-id",
        default=None,
        help="skip collection and start from extract with this run_id (requires prior collect)",
    )
    p_pipe.add_argument(
        "--max-items",
        type=int,
        default=None,
        help="cap items from source (default: APIFY_MAX_ITEMS_PER_RUN). "
        "0 or negative = no cap for apify_data/fixture (entire file).",
    )
    p_pipe.add_argument(
        "--username",
        action="append",
        default=[],
        help="seed handle for COLLECTION_MODE=apify (repeatable)",
    )
    p_pipe.add_argument(
        "--seed-handle",
        action="append",
        default=[],
        help="Deprecated alias for --username.",
    )
    p_pipe.add_argument("-v", "--verbose", action="store_true")

    args = parser.parse_args(argv)

    if args.version:
        print(__version__)
        return 0

    if args.command == "validate-fixtures":
        path = args.path or _default_fixture_path()
        if not path.is_file():
            print(f"error: fixture file not found: {path}", file=sys.stderr)
            return 1
        return cmd_validate_fixtures(path, verbose=args.verbose)

    if args.command == "show-config":
        return cmd_show_config(verbose=args.verbose)

    if args.command == "collect":
        usernames = list(args.username) + list(args.seed_handle)
        return cmd_collect(
            max_items=args.max_items,
            usernames=usernames,
            verbose=args.verbose,
        )

    if args.command == "extract":
        return cmd_extract(
            run_id=args.run_id,
            verbose=args.verbose,
            show_relations=args.show_relations,
        )

    if args.command == "dedup":
        return cmd_dedup(
            run_id=args.run_id,
            verbose=args.verbose,
            show_pairs=args.show_pairs,
        )

    if args.command == "graph-insert":
        return cmd_graph_insert(
            run_id=args.run_id,
            verbose=args.verbose,
        )

    if args.command == "quality":
        return cmd_quality(
            run_id=args.run_id,
            verbose=args.verbose,
        )

    if args.command == "query":
        return cmd_query(
            question=args.question,
            verbose=args.verbose,
            show_cypher=args.show_cypher,
        )

    if args.command == "graph-wipe":
        return cmd_graph_wipe(yes=args.yes, verbose=args.verbose)

    if args.command == "local-reset":
        return cmd_local_reset(yes=args.yes, verbose=args.verbose)

    if args.command == "pipeline":
        usernames = list(args.username) + list(args.seed_handle)
        return cmd_pipeline(
            run_id=args.run_id,
            max_items=args.max_items,
            usernames=usernames,
            verbose=args.verbose,
        )

    parser.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
