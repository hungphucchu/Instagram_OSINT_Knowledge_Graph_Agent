"""Unit tests for ``src/myproject/retriever.py``."""

from __future__ import annotations

from typing import Any

from myproject.retriever import Retriever


class _FakeStore:
    def __init__(self, rows: list[dict[str, Any]]) -> None:
        self._rows = rows
        self.calls: list[tuple[str, Any]] = []
        self.closed = False

    def run_read(self, query: str, params: Any = None) -> list[dict[str, Any]]:
        self.calls.append((query, params))
        if "count(n)" in query:
            return [{"c": len(self._rows)}]
        if "count(r)" in query:
            return [{"c": max(0, len(self._rows) - 1)}]
        if "UNWIND labels(n) AS label" in query:
            return [{"name": "CanonicalEntity", "count": 2}, {"name": "Post", "count": 1}]
        if "RETURN type(r) AS name" in query:
            return [{"name": "MENTIONS", "count": 3}]
        if "MATCH (e:CanonicalEntity)" in query:
            return [
                {
                    "node_id": "ent_1",
                    "display_name": "Alice",
                    "entity_kind": "Person",
                    "alias_count": 2,
                    "mention_count": 5,
                    "source_run_id": "run_123",
                }
            ]
        if "MATCH (a)-[r]->(b)" in query:
            return [
                {
                    "rel_type": "MENTIONS",
                    "source_id": "ent_1",
                    "source_display": "Alice",
                    "source_labels": ["CanonicalEntity"],
                    "target_id": "post_1",
                    "target_display": "post_1",
                    "target_labels": ["Post"],
                    "artifact_id": "art_1",
                    "confidence": 0.9,
                }
            ]
        return list(self._rows)

    def close(self) -> None:
        self.closed = True


def test_retriever_module_imports() -> None:
    import myproject.retriever  # noqa: F401


def test_retriever_search_caps_to_k() -> None:
    rows = [{"id": i} for i in range(10)]
    retriever = Retriever()
    retriever._store = _FakeStore(rows)
    result = retriever.search("MATCH (n) RETURN n LIMIT 50", k=3)
    assert len(result) == 3
    assert result[0]["id"] == 0


def test_retriever_search_returns_empty_on_error() -> None:
    class _Boom:
        def run_read(self, *_a, **_kw):  # noqa: ANN001
            raise RuntimeError("syntax")

    retriever = Retriever()
    retriever._store = _Boom()
    assert retriever.search("MATCH (n) RETURN n", k=5) == []


def test_retriever_graph_stats_returns_ints() -> None:
    retriever = Retriever()
    retriever._store = _FakeStore(rows=[{"a": 1}, {"a": 2}])
    stats = retriever.graph_stats()
    assert stats == {"nodes": 2, "edges": 1}


def test_retriever_graph_overview_returns_rich_tables() -> None:
    retriever = Retriever()
    retriever._store = _FakeStore(rows=[{"a": 1}, {"a": 2}])
    overview = retriever.graph_overview(relationship_type="MENTIONS")

    assert overview["nodes"] == 2
    assert overview["edges"] == 1
    assert overview["node_labels"][0] == {"name": "CanonicalEntity", "count": 2}
    assert overview["relationship_types"][0] == {"name": "MENTIONS", "count": 3}
    assert overview["entities"][0]["display_name"] == "Alice"
    assert overview["relationships"][0]["rel_type"] == "MENTIONS"


def test_retriever_close_is_idempotent() -> None:
    retriever = Retriever()
    fake = _FakeStore(rows=[])
    retriever._store = fake
    retriever.close()
    assert fake.closed is True
    # Second close is a no-op
    retriever.close()
