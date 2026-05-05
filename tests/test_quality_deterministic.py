from __future__ import annotations

from agents.quality.deterministic_checks import evaluate_deterministic


class _Graph:
    def __init__(self, rows_map):
        self.rows_map = rows_map

    def run_read(self, query, params=None):
        if "missing source_run_id" in query:
            return []
        if "MATCH (n)" in query and "source_run_id IS NULL" in query:
            return self.rows_map.get("missing_node_prov", [])
        if "MATCH ()-[r]->()" in query and "source_run_id IS NULL" in query:
            return self.rows_map.get("missing_rel_prov", [])
        if "WITH a.node_id AS from_id" in query:
            return self.rows_map.get("dup_edges", [])
        if "AND NOT (n)--()" in query:
            return self.rows_map.get("orphans", [])
        if "MATCH (n:Post)" in query:
            return self.rows_map.get("post_times", [])
        return []


class _Raw:
    def __init__(self, ids):
        self.ids = ids

    def list_by_run(self, run_id):
        return [type("R", (), {"artifact_id": x})() for x in self.ids]


class _Ext:
    def __init__(self, ids):
        self.ids = ids

    def list_by_run(self, run_id):
        return [type("E", (), {"artifact_id": x})() for x in self.ids]


def test_deterministic_flags_critical_issues():
    graph = _Graph(
        {
            "missing_node_prov": [{"id": "n1"}],
            "missing_rel_prov": [{"id": "r1"}],
            "dup_edges": [{"from_id": "a", "to_id": "b", "rel_type": "X", "c": 2}],
            "orphans": [{"id": "n2"}],
            "post_times": [{"id": "p1", "collected_at": "not-a-time"}],
        }
    )
    raw = _Raw(["a1"])
    ext = _Ext(["a1", "a2"])
    out = evaluate_deterministic(run_id="r", graph_store=graph, raw_store=raw, extraction_store=ext)
    ids = {x.rule_id for x in out}
    assert "missing_node_provenance" in ids
    assert "missing_relationship_provenance" in ids
    assert "duplicate_conflicting_edges" in ids
    assert "orphan_nodes" in ids
    assert "invalid_post_timestamps" in ids
    assert "sqlite_extraction_missing_raw_artifact" in ids
    sev = {v.rule_id: v.severity for v in out}
    assert sev["duplicate_conflicting_edges"] == "critical"
    assert sev["orphan_nodes"] == "warning"


def test_deterministic_mentions_duplicates_are_warning():
    graph = _Graph(
        {
            "dup_edges": [{"from_id": "a", "to_id": "b", "rel_type": "MENTIONS", "c": 3}],
            "orphans": [],
            "post_times": [],
        }
    )
    out = evaluate_deterministic(
        run_id="r", graph_store=graph, raw_store=_Raw([]), extraction_store=_Ext([])
    )
    assert any(v.rule_id == "duplicate_mentions_edges" and v.severity == "warning" for v in out)
