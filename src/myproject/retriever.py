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

    def close(self) -> None:
        if self._store is not None and hasattr(self._store, "close"):
            try:
                self._store.close()
            finally:
                self._store = None
