"""Neo4j graph backend for Phase 4."""

from __future__ import annotations

import contextlib
from typing import Any


class Neo4jGraphStore:
    """Idempotent upsert store for graph nodes and relationships in Neo4j."""

    def __init__(self, *, uri: str, user: str, password: str, database: str) -> None:
        if not uri or not user or not password:
            raise ValueError("NEO4J_URI, NEO4J_USER, and NEO4J_PASSWORD are required for GRAPH_BACKEND=neo4j")
        try:
            from neo4j import GraphDatabase
        except ImportError as exc:
            raise ImportError("neo4j package is required for GRAPH_BACKEND=neo4j") from exc
        self._driver = GraphDatabase.driver(uri, auth=(user, password))
        self._database = database or "neo4j"

    def ensure_constraints(self) -> None:
        # One label for dedup clusters so MERGE on node_id cannot split the same canonical_id across Person/Org/...
        statements = [
            "CREATE CONSTRAINT canonical_entity_node_id IF NOT EXISTS "
            "FOR (n:CanonicalEntity) REQUIRE n.node_id IS UNIQUE",
            "CREATE CONSTRAINT post_platform_post_id IF NOT EXISTS FOR (n:Post) REQUIRE n.platform_post_id IS UNIQUE",
            "CREATE CONSTRAINT artifact_artifact_id IF NOT EXISTS FOR (n:Artifact) REQUIRE n.artifact_id IS UNIQUE",
            "CREATE CONSTRAINT node_node_id IF NOT EXISTS FOR (n:GraphNode) REQUIRE n.node_id IS UNIQUE",
        ]
        with self._driver.session(database=self._database) as session:
            for statement in statements:
                session.run(statement)

    def upsert_node(
        self,
        *,
        node_id: str,
        label: str,
        properties: dict[str, Any],
        source_run_id: str,
    ) -> bool:
        node_label = self._safe_label(label)
        payload = {
            "node_id": node_id,
            "properties": properties,
            "source_run_id": source_run_id,
        }
        query = f"""
        MERGE (n:{node_label} {{node_id: $node_id}})
        ON CREATE SET n += $properties, n.source_run_id = $source_run_id, n._created = true
        ON MATCH SET n += $properties, n.source_run_id = $source_run_id, n._created = false
        RETURN n._created AS created
        """
        with self._driver.session(database=self._database) as session:
            record = session.run(query, payload).single()
        return bool(record and record["created"])

    def upsert_relationship(
        self,
        *,
        rel_id: str,
        rel_type: str,
        from_node_id: str,
        to_node_id: str,
        properties: dict[str, Any],
        source_run_id: str,
    ) -> bool:
        edge_type = self._safe_label(rel_type)
        payload = {
            "rel_id": rel_id,
            "from_node_id": from_node_id,
            "to_node_id": to_node_id,
            "properties": properties,
            "source_run_id": source_run_id,
        }
        # LIMIT 1 per end: legacy data could duplicate node_id across labels; avoid multi-row MERGE.
        query = f"""
        MATCH (a {{node_id: $from_node_id}})
        WITH a LIMIT 1
        MATCH (b {{node_id: $to_node_id}})
        WITH a, b LIMIT 1
        MERGE (a)-[r:{edge_type} {{rel_id: $rel_id}}]->(b)
        ON CREATE SET r += $properties, r.source_run_id = $source_run_id, r._created = true
        ON MATCH SET r += $properties, r.source_run_id = $source_run_id, r._created = false
        RETURN r._created AS created
        """
        with self._driver.session(database=self._database) as session:
            record = session.run(query, payload).single()
        return bool(record and record["created"])

    def count_nodes(self) -> int:
        with self._driver.session(database=self._database) as session:
            row = session.run("MATCH (n) RETURN count(n) AS c").single()
        return int(row["c"] if row else 0)

    def count_relationships(self) -> int:
        with self._driver.session(database=self._database) as session:
            row = session.run("MATCH ()-[r]->() RETURN count(r) AS c").single()
        return int(row["c"] if row else 0)

    def run_read(self, query: str, params: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        payload = params or {}
        with self._driver.session(database=self._database) as session:
            result = session.run(query, payload)
            return [dict(record) for record in result]

    def close(self) -> None:
        self._driver.close()

    @staticmethod
    def _safe_label(value: str) -> str:
        out = "".join(ch if ch.isalnum() or ch == "_" else "_" for ch in value)
        if not out:
            return "GraphNode"
        return out

    def __del__(self) -> None:
        with contextlib.suppress(Exception):
            self.close()

