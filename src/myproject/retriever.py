"""Retriever — thin facade over Neo4j read-only graph access.

The spec (``docs/SPEC.md`` §4.2) declares ``Retriever.search(query, k)`` as the
public contract. Internally we delegate to the existing Neo4j store under
``src/agents/graph_insertion/``. The retriever is also responsible for opening
connections lazily so unit tests can construct the class without a live DB.
"""

from __future__ import annotations

import logging
from typing import Any

from myproject.logging_setup import log_event

LOG = logging.getLogger("myproject.retriever")


class Retriever:
    """Read-only Neo4j retriever.

    Parameters mirror what the rubric SPEC declares so that regenerated code
    can drop in cleanly.
    """

    def __init__(self, index_path: str = "bolt://localhost:7687") -> None:
        self.index_path = index_path
        self._store: Any | None = None

    # ------------------------------------------------------------------
    # Lazy connection
    # ------------------------------------------------------------------
    def _connect(self) -> Any:
        if self._store is not None:
            return self._store
        from agents.graph_insertion import Neo4jGraphStore  # noqa: WPS433
        from config import get_settings  # noqa: WPS433

        settings = get_settings()
        self._store = Neo4jGraphStore(
            uri=settings.neo4j_uri or self.index_path,
            user=settings.neo4j_user,
            password=settings.neo4j_password,
            database=settings.neo4j_database,
        )
        return self._store

    # ------------------------------------------------------------------
    # Public API (SPEC §4.2)
    # ------------------------------------------------------------------
    def search(self, query: str, k: int = 5) -> list[dict[str, Any]]:
        """Run a read-only Cypher and return at most ``k`` rows.

        ``query`` is expected to already be a safe Cypher string (the Router
        is responsible for verification via ``cypher_guard``). Failures are
        logged and surfaced as an empty list so callers can still respond.
        """
        store = self._connect()
        try:
            rows = store.run_read(query, None)
        except Exception as exc:  # pragma: no cover - exercised in integration
            log_event(LOG, "retriever_failed", level=logging.WARNING, error=str(exc), k=k)
            return []
        log_event(LOG, "retriever_search_complete", k=k, hits=len(rows))
        return list(rows)[:k]

    def graph_stats(self) -> dict[str, int]:
        """Cheap summary used by health/stats endpoints and demo scripts."""
        store = self._connect()
        try:
            node_rows = store.run_read("MATCH (n) RETURN count(n) AS c", None)
            edge_rows = store.run_read("MATCH ()-[r]->() RETURN count(r) AS c", None)
        except Exception as exc:  # pragma: no cover
            log_event(LOG, "retriever_stats_failed", level=logging.WARNING, error=str(exc))
            return {"nodes": 0, "edges": 0}
        return {
            "nodes": int((node_rows or [{}])[0].get("c", 0) or 0),
            "edges": int((edge_rows or [{}])[0].get("c", 0) or 0),
        }

    def graph_overview(
        self,
        *,
        relationship_type: str | None = None,
        entity_limit: int = 50,
        relationship_limit: int = 200,
    ) -> dict[str, Any]:
        """Return richer graph metadata for the frontend operator console."""
        store = self._connect()
        try:
            stats = self.graph_stats()
            label_rows = store.run_read(
                """
                MATCH (n)
                UNWIND labels(n) AS label
                RETURN label AS name, count(*) AS count
                ORDER BY count DESC, name ASC
                """,
                None,
            )
            relationship_counts = store.run_read(
                """
                MATCH ()-[r]->()
                RETURN type(r) AS name, count(*) AS count
                ORDER BY count DESC, name ASC
                """,
                None,
            )
            entities = store.run_read(
                """
                MATCH (e:CanonicalEntity)
                RETURN
                  e.node_id AS node_id,
                  coalesce(e.canonical_surface, e.node_id) AS display_name,
                  coalesce(e.entity_kind, "Entity") AS entity_kind,
                  size(coalesce(e.aliases, [])) AS alias_count,
                  size(coalesce(e.mention_ids, [])) AS mention_count,
                  e.source_run_id AS source_run_id
                ORDER BY mention_count DESC, display_name ASC
                LIMIT $limit
                """,
                {"limit": max(1, entity_limit)},
            )
            relationships = store.run_read(
                """
                MATCH (a)-[r]->(b)
                WHERE $rel_type IS NULL OR type(r) = $rel_type
                RETURN
                  type(r) AS rel_type,
                  a.node_id AS source_id,
                  coalesce(a.canonical_surface, a.platform_post_id, a.artifact_id, a.node_id) AS source_display,
                  labels(a) AS source_labels,
                  b.node_id AS target_id,
                  coalesce(b.canonical_surface, b.platform_post_id, b.artifact_id, b.node_id) AS target_display,
                  labels(b) AS target_labels,
                  r.artifact_id AS artifact_id,
                  r.confidence AS confidence
                ORDER BY rel_type ASC, source_display ASC, target_display ASC
                LIMIT $limit
                """,
                {
                    "rel_type": relationship_type or None,
                    "limit": max(1, relationship_limit),
                },
            )
        except Exception as exc:  # pragma: no cover
            log_event(LOG, "retriever_overview_failed", level=logging.WARNING, error=str(exc))
            return {
                "nodes": 0,
                "edges": 0,
                "node_labels": [],
                "relationship_types": [],
                "entities": [],
                "relationships": [],
            }

        return {
            **stats,
            "node_labels": [
                {"name": str(row.get("name") or ""), "count": int(row.get("count") or 0)}
                for row in label_rows
            ],
            "relationship_types": [
                {"name": str(row.get("name") or ""), "count": int(row.get("count") or 0)}
                for row in relationship_counts
            ],
            "entities": [
                {
                    "node_id": str(row.get("node_id") or ""),
                    "display_name": str(row.get("display_name") or ""),
                    "entity_kind": str(row.get("entity_kind") or "Entity"),
                    "alias_count": int(row.get("alias_count") or 0),
                    "mention_count": int(row.get("mention_count") or 0),
                    "source_run_id": row.get("source_run_id"),
                }
                for row in entities
            ],
            "relationships": [
                {
                    "rel_type": str(row.get("rel_type") or ""),
                    "source_id": str(row.get("source_id") or ""),
                    "source_display": str(row.get("source_display") or ""),
                    "source_labels": list(row.get("source_labels") or []),
                    "target_id": str(row.get("target_id") or ""),
                    "target_display": str(row.get("target_display") or ""),
                    "target_labels": list(row.get("target_labels") or []),
                    "artifact_id": row.get("artifact_id"),
                    "confidence": row.get("confidence"),
                }
                for row in relationships
            ],
        }

    def close(self) -> None:
        if self._store is not None and hasattr(self._store, "close"):
            try:
                self._store.close()
            finally:
                self._store = None
