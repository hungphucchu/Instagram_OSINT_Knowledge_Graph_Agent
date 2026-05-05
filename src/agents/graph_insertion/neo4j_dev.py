"""Dev-only helpers for Neo4j (not used in production ingest)."""

from __future__ import annotations


def wipe_all_graph_data(*, uri: str, user: str, password: str, database: str) -> None:
    """Remove every node and relationship in the configured database."""
    if not uri or not user or not password:
        raise ValueError("NEO4J_URI, NEO4J_USER, and NEO4J_PASSWORD are required")
    try:
        from neo4j import GraphDatabase
    except ImportError as exc:
        raise ImportError("neo4j package is required") from exc
    driver = GraphDatabase.driver(uri, auth=(user, password))
    db = database or "neo4j"
    try:
        with driver.session(database=db) as session:
            session.run("MATCH (n) DETACH DELETE n")
    finally:
        driver.close()
