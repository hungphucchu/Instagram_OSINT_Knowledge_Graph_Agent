"""Sample pipeline runner.

The Makefile target ``make reproduce`` runs ``python -m myproject.pipeline
--sample`` to exercise the full ingest path on a tiny fixture so the TA can
validate end-to-end behaviour on a clean machine without spending API credits.

The ``run_sample_ingest`` helper is also called by ``POST /api/pipeline/sample``
(see ``docs/STORIES.md`` US-04) and returns a JSON-friendly summary the UI can
display.

Internally the heavy lifting is delegated to the existing ingest agents under
``src/agents/``; this module only prepares inputs, calls them, and reports.
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path
from typing import Any

from myproject.logging_setup import (
    configure_logging,
    log_event,
    new_request_id,
    reset_request_id,
    set_request_id,
)

LOG = logging.getLogger("myproject.pipeline")


def _fixture_path() -> Path:
    here = Path(__file__).resolve()
    # src/myproject/pipeline.py -> repo root is parents[2]
    return here.parents[2] / "fixtures" / "raw_artifacts.json"


def run_sample_ingest(*, fixture: Path | None = None) -> dict[str, Any]:
    """Run the ingest pipeline on a single, deterministic fixture.

    Returns
    -------
    dict
        ``{"run_id": str, "raw_artifacts": int, "extraction_records": int,
        "dedup_clusters": int}``.
    """
    configure_logging()
    log_id = new_request_id()
    token = set_request_id(log_id)
    try:
        path = fixture or _fixture_path()
        log_event(LOG, "sample_ingest_starting", fixture=str(path))
        rows = json.loads(path.read_text(encoding="utf-8"))

        from agents.collection import RawArtifactStore  # noqa: WPS433
        from config import get_settings  # noqa: WPS433
        from schemas.raw_artifact import RawArtifact  # noqa: WPS433

        settings = get_settings()
        settings.collection_db_path.parent.mkdir(parents=True, exist_ok=True)
        raw_store = RawArtifactStore(db_path=settings.collection_db_path)
        artifacts = [RawArtifact.model_validate(r) for r in rows]
        raw_store.upsert_many(artifacts)
        # All fixture rows share the same run_id; use it to drive extraction + dedup.
        run_id = artifacts[0].run_id if artifacts else log_id
        log_event(LOG, "sample_ingest_raw_loaded", count=len(artifacts), run_id=run_id)

        from agents.deduplication import DedupAgent, DedupStore  # noqa: WPS433
        from agents.extraction import ExtractionAgent, ExtractionStore  # noqa: WPS433

        ext_store = ExtractionStore(db_path=settings.extraction_db_path)
        ext_agent = ExtractionAgent(
            raw_store=raw_store,
            extraction_store=ext_store,
            mode="heuristic",
            llm_provider="openai",
            llm_model="",
            llm_base_url="",
            llm_api_key="",
            llm_timeout_seconds=30,
            max_concurrency=1,
        )
        ext_result = ext_agent.run(run_id=run_id)
        extraction_count = int(getattr(ext_result, "records_written", 0) or 0)

        dedup_store = DedupStore(db_path=settings.dedup_db_path)
        dedup_agent = DedupAgent(
            extraction_store=ext_store,
            dedup_store=dedup_store,
            embedding_backend="char_ngram",
            fuzzy_merge_threshold=0.90,
            embedding_merge_threshold=0.82,
            fuzzy_review_threshold=0.78,
            char_ngram_n=3,
        )
        dedup_result = dedup_agent.run(run_id=run_id)
        cluster_count = int(
            getattr(dedup_result, "clusters_written", None)
            or len(getattr(dedup_result, "clusters", []) or [])
        )

        try:
            from agents.graph_insertion import GraphInsertionAgent, Neo4jGraphStore  # noqa: WPS433

            graph_store = Neo4jGraphStore(
                uri=settings.neo4j_uri,
                user=settings.neo4j_user,
                password=settings.neo4j_password,
                database=settings.neo4j_database,
            )
            try:
                graph_agent = GraphInsertionAgent(
                    graph_backend="neo4j",
                    graph_store=graph_store,
                    raw_store=raw_store,
                    extraction_store=ext_store,
                    dedup_store=dedup_store,
                )
                graph_result = graph_agent.run(run_id=run_id)
                log_event(
                    LOG,
                    "sample_ingest_graph_complete",
                    status=graph_result.status,
                    nodes_created=graph_result.nodes_created,
                    relationships_created=graph_result.relationships_created,
                )
            finally:
                graph_store.close()
        except Exception as exc:
            log_event(
                LOG,
                "sample_ingest_graph_skipped",
                level=logging.WARNING,
                error=str(exc),
            )

        log_event(
            LOG,
            "sample_ingest_complete",
            raw=len(artifacts),
            extraction=extraction_count,
            clusters=cluster_count,
        )
        return {
            "run_id": run_id,
            "raw_artifacts": len(artifacts),
            "extraction_records": extraction_count,
            "dedup_clusters": cluster_count,
        }
    finally:
        reset_request_id(token)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Instagram OSINT KG sample pipeline")
    parser.add_argument(
        "--sample",
        action="store_true",
        help="Run the deterministic sample ingest (used by `make reproduce`).",
    )
    parser.add_argument("--fixture", type=Path, default=None, help="Override fixture path.")
    args = parser.parse_args(argv)

    if not args.sample:
        parser.error("--sample is required (other modes go through the full CLI under `cli`)")

    summary = run_sample_ingest(fixture=args.fixture)
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
