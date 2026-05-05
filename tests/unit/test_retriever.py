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


def test_retriever_close_is_idempotent() -> None:
    retriever = Retriever()
    fake = _FakeStore(rows=[])
    retriever._store = fake
    retriever.close()
    assert fake.closed is True
    # Second close is a no-op
    retriever.close()
