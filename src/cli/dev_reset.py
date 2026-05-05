"""Dev-only full local reset (SQLite pipeline DBs + Neo4j)."""

from __future__ import annotations

import logging
import sys
from pathlib import Path

from agents.graph_insertion.neo4j_dev import wipe_all_graph_data
from agents.graph_insertion.neo4j_graph_store import Neo4jGraphStore
from config import Settings, get_settings


def _unlink_sqlite_bundle(path: Path, *, verbose: bool) -> None:
    for candidate in (path, Path(f"{path}-wal"), Path(f"{path}-shm")):
        if candidate.is_file():
            candidate.unlink()
            if verbose:
                print(f"deleted {candidate}")


def run_local_reset(*, settings: Settings | None = None, verbose: bool = False) -> int:
    """Delete pipeline SQLite files and wipe Neo4j. Returns 0 on full success."""
    s = settings or get_settings()
    if verbose:
        logging.basicConfig(level=logging.INFO)
        logging.getLogger("cli.dev_reset").info(
            "local_reset sqlite=%s %s %s neo4j_db=%s",
            s.collection_db_path,
            s.extraction_db_path,
            s.dedup_db_path,
            s.neo4j_database,
        )
    for p in (s.collection_db_path, s.extraction_db_path, s.dedup_db_path):
        _unlink_sqlite_bundle(Path(p), verbose=verbose)

    if s.graph_backend != "neo4j":
        print("local_reset_sqlite_ok (neo4j skip: GRAPH_BACKEND is not neo4j)")
        get_settings.cache_clear()
        return 0

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
        n, r = store.count_nodes(), store.count_relationships()
    finally:
        store.close()
    get_settings.cache_clear()
    print(f"local_reset_ok sqlite_cleared neo4j_nodes_remaining={n} neo4j_rels_remaining={r}")
    if n != 0 or r != 0:
        print("warning: Neo4j not empty after wipe; check NEO4J_DATABASE / credentials.", file=sys.stderr)
        return 1
    return 0
