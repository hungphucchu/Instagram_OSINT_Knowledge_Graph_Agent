from __future__ import annotations

from agents.query import QueryAgent, QueryRequest, verify_read_only_cypher
from config import Settings


class FakeGraphStore:
    def __init__(self, rows=None):
        self.rows = rows or []
        self.last_query = ""

    def run_read(self, query, params=None):
        self.last_query = query
        if "DISTINCT labels" in query:
            return [{"labels": ["CanonicalEntity"]}, {"labels": ["Post"]}]
        if "DISTINCT type" in query:
            return [{"type": "MENTIONS"}]
        return self.rows


class ExplodingGraphStore(FakeGraphStore):
    def run_read(self, query, params=None):
        if "DISTINCT labels" in query or "DISTINCT type" in query:
            return super().run_read(query, params)
        raise RuntimeError("neo4j syntax error")


class FakeNode:
    def __init__(self, data):
        self._data = data

    def __iter__(self):
        return iter(self._data.items())


def test_guard_blocks_mutation():
    ok, _, err = verify_read_only_cypher("MATCH (n) DELETE n RETURN n", max_limit=50)
    assert ok is False
    assert "mutating" in (err or "")


def test_guard_adds_limit():
    ok, q, _ = verify_read_only_cypher("MATCH (n) RETURN n.node_id AS node_id", max_limit=25)
    assert ok is True
    assert "LIMIT 25" in q


def test_guard_rejects_malformed_return_clause():
    ok, _, err = verify_read_only_cypher("MATCH (p:CanonicalEntity) RETURN", max_limit=50)
    assert ok is False
    assert "malformed RETURN" in (err or "")


def test_query_agent_empty_graph_returns_no_evidence(tmp_path):
    settings = Settings(
        collection_db_path=tmp_path / "raw.db",
        extraction_db_path=tmp_path / "ext.db",
        dedup_db_path=tmp_path / "ded.db",
        query_llm_enabled=False,
        query_llm_api_key="",
    )
    agent = QueryAgent(settings=settings, graph_store=FakeGraphStore(rows=[]))
    resp = agent.answer(QueryRequest(question="who appears most"))
    assert "No evidence found in the graph for this question." in resp.answer
    assert resp.evidence == []


def test_query_agent_uses_llm_generated_cypher():
    settings = Settings(query_llm_enabled=True, query_llm_api_key="k")
    rows = [{"from_id": "a", "to_id": "b", "from_name": "Alice", "to_name": "Bob", "freq": 4}]
    fake = FakeGraphStore(rows=rows)
    agent = QueryAgent(settings=settings, graph_store=fake)
    agent._generate_cypher_llm = lambda _: (  # type: ignore[method-assign]
        "MATCH (a:CanonicalEntity)-[r:MENTIONS]->(b:CanonicalEntity) "
        "RETURN a.node_id AS from_id, b.node_id AS to_id, "
        "coalesce(a.canonical_surface, a.node_id) AS from_name, "
        "coalesce(b.canonical_surface, b.node_id) AS to_name, count(r) AS freq "
        "ORDER BY freq DESC LIMIT 10"
    )
    agent._synthesize_answer_llm = lambda *_: "Most frequent mention is Alice -> Bob."  # type: ignore[method-assign]
    resp = agent.answer(QueryRequest(question="who mention who most", include_cypher=True))
    assert "Most frequent mention is Alice -> Bob." in resp.answer
    assert resp.evidence
    assert "from_name" in (resp.cypher or "")
    assert "MATCH" in (resp.cypher or "")


def test_query_agent_falls_back_to_generic_query_without_llm():
    settings = Settings(query_llm_enabled=False, query_llm_api_key="")
    rows = [{"node_id": "n1"}]
    fake = FakeGraphStore(rows=rows)
    agent = QueryAgent(settings=settings, graph_store=fake)
    resp = agent.answer(QueryRequest(question="show me all person name", include_cypher=True))
    assert "Found 1 evidence row(s)." in resp.answer
    assert "node_id" in (resp.cypher or "")


def test_query_agent_uses_deterministic_coappearance_query_without_llm():
    settings = Settings(query_llm_enabled=False, query_llm_api_key="")
    rows = [
        {
            "entity_a": "demo_user",
            "entity_b": "utsa_ai_lab",
            "shared_posts": 1,
            "post_ids": ["C9DEMO001"],
        }
    ]
    fake = FakeGraphStore(rows=rows)
    agent = QueryAgent(settings=settings, graph_store=fake)
    resp = agent.answer(
        QueryRequest(question="Who appeared together most often?", include_cypher=True)
    )
    assert "Found 1 evidence row(s)." in resp.answer
    assert "shared_posts" in (resp.cypher or "")


def test_query_agent_json_safe_evidence_for_node_like_values():
    settings = Settings(query_llm_enabled=False, query_llm_api_key="")
    rows = [{"p": FakeNode({"canonical_surface": "Alice"})}]
    fake = FakeGraphStore(rows=rows)
    agent = QueryAgent(settings=settings, graph_store=fake)
    resp = agent.answer(QueryRequest(question="show me all person"))
    assert isinstance(resp.evidence[0]["p"], dict)


def test_query_agent_llm_translation_failure_uses_generic_fallback():
    settings = Settings(query_llm_enabled=True, query_llm_api_key="k")
    rows = [{"node_id": "n1"}]
    fake = FakeGraphStore(rows=rows)
    agent = QueryAgent(settings=settings, graph_store=fake)
    agent._generate_cypher_llm = lambda _: "not-json-response"  # type: ignore[method-assign]
    resp = agent.answer(QueryRequest(question="who mention who most"))
    assert "safe read-only graph query" in resp.answer
    assert "query must include MATCH/WITH and RETURN" in " ".join(resp.warnings)


def test_query_agent_answer_synthesis_falls_back_to_row_count():
    settings = Settings(query_llm_enabled=True, query_llm_api_key="k")
    rows = [{"entity1": "I", "entity2": "my wife", "coappearances": 10}]
    fake = FakeGraphStore(rows=rows)
    agent = QueryAgent(settings=settings, graph_store=fake)
    agent._generate_cypher_llm = lambda _: "MATCH (n) RETURN n.node_id AS node_id LIMIT 10"  # type: ignore[method-assign]

    def _boom(*_args, **_kwargs):
        raise ValueError("bad payload")

    agent._synthesize_answer_llm = _boom  # type: ignore[method-assign]
    resp = agent.answer(QueryRequest(question="top co-appears"))
    assert "Found 1 evidence row(s)." in resp.answer
    assert any("llm_answer_synthesis_failed_fallback" in w for w in resp.warnings)


def test_query_agent_rejects_no_evidence_phrase_when_rows_exist():
    settings = Settings(query_llm_enabled=True, query_llm_api_key="k")
    rows = [{"name": "NASA", "mentions_count": 7}]
    fake = FakeGraphStore(rows=rows)
    agent = QueryAgent(settings=settings, graph_store=fake)
    agent._generate_cypher_llm = lambda _: "MATCH (n) RETURN n.node_id AS node_id LIMIT 10"  # type: ignore[method-assign]
    agent._synthesize_answer_llm = lambda *_: "No evidence found in the graph for this question."  # type: ignore[method-assign]
    resp = agent.answer(QueryRequest(question="most famous person"))
    assert "Found 1 evidence row(s)." in resp.answer
    assert any("llm_answer_synthesis_failed_fallback" in w for w in resp.warnings)


def test_query_agent_handles_query_execution_error():
    settings = Settings(query_llm_enabled=False, query_llm_api_key="")
    agent = QueryAgent(settings=settings, graph_store=ExplodingGraphStore(rows=[]))
    resp = agent.answer(QueryRequest(question="most famous person", include_cypher=True))
    assert "could not execute the generated graph query safely" in resp.answer.lower()
    assert any("query_execution_failed" in w for w in resp.warnings)


def test_query_agent_repairs_count_brace_syntax():
    raw = (
        "MATCH (c1:CanonicalEntity)-[:COLLABORATES_WITH]->(c2:CanonicalEntity) "
        "RETURN COUNT({(c1)-[:COLLABORATES_WITH]->(c2)}) AS co_occurrence_count"
    )
    fixed = QueryAgent._repair_generated_cypher(raw)
    assert "COUNT({(" not in fixed
    assert "COUNT { (c1)-[:COLLABORATES_WITH]->(c2) }" in fixed
