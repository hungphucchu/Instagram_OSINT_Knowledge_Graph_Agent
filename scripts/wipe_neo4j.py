#!/usr/bin/env python3
"""Dev: wipe every node and relationship from Neo4j (same settings as `cli graph-wipe`).

Usage (from repo root):

  PYTHONPATH=src python scripts/wipe_neo4j.py --yes

Requires NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD (and optional NEO4J_DATABASE) in `.env`.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


def main() -> int:
    repo = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(repo / "src"))

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--yes",
        action="store_true",
        help="required safeguard; runs MATCH (n) DETACH DELETE n",
    )
    args = parser.parse_args()
    if not args.yes:
        print("error: pass --yes to confirm full graph delete", file=sys.stderr)
        return 1

    from agents.graph_insertion.neo4j_dev import wipe_all_graph_data
    from agents.graph_insertion.neo4j_graph_store import Neo4jGraphStore
    from config import get_settings

    s = get_settings()
    if s.graph_backend != "neo4j":
        print("error: GRAPH_BACKEND must be neo4j", file=sys.stderr)
        return 1
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
    print(f"graph_wipe_ok nodes_remaining={n} relationships_remaining={r}")
    return 0 if n == 0 and r == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
