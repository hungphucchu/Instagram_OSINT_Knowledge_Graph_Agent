"use client";

import { useEffect, useState } from "react";

import type {
  GraphOverviewResponse,
  GraphRelationshipRow
} from "@/lib/types";

async function fetchGraphOverview(relationshipType: string): Promise<GraphOverviewResponse> {
  const res = await fetch(`/api/graph/overview${relationshipType ? `?relationship_type=${relationshipType}` : ""}`);
  const data = await res.json();
  if (!res.ok) {
    throw new Error(data.error || "Failed to load graph overview");
  }
  return data as GraphOverviewResponse;
}

export default function GraphPage() {
  const [overview, setOverview] = useState<GraphOverviewResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [selectedRelationshipType, setSelectedRelationshipType] = useState("");

  async function refreshOverview({
    relationshipType = selectedRelationshipType,
    silent = false
  }: {
    relationshipType?: string;
    silent?: boolean;
  } = {}) {
    if (!silent) {
      setLoading(true);
      setError("");
    }
    try {
      setOverview(await fetchGraphOverview(relationshipType));
    } catch (err) {
      if (!silent) {
        setError(err instanceof Error ? err.message : "Unknown error");
      }
    } finally {
      if (!silent) {
        setLoading(false);
      }
    }
  }

  useEffect(() => {
    async function loadInitialOverview() {
      try {
        setOverview(await fetchGraphOverview(""));
      } catch (_err) {
        // Keep the page usable even if the graph is still empty or booting.
      }
    }

    void loadInitialOverview();
  }, []);

  async function onRelationshipChange(nextType: string) {
    setSelectedRelationshipType(nextType);
    await refreshOverview({ relationshipType: nextType });
  }

  const statRows = [
    { label: "Backend Version", value: overview?.version ?? "—" },
    { label: "Nodes", value: overview?.nodes ?? "—" },
    { label: "Edges", value: overview?.edges ?? "—" }
  ];

  const relationships = overview?.relationships ?? [];

  return (
    <section className="stack">
      <div>
        <h2>Graph Explorer</h2>
        <p className="muted">
          Inspect the structural integrity and content of the knowledge graph, including entities,
          provenance, and semantic relationships.
        </p>
      </div>

      <div className="grid-three">
        <div className="card metric-card">
          <span className="metric-label">Nodes</span>
          <strong className="metric-value">{overview?.nodes ?? "—"}</strong>
          <div className="metric-sub">Total Entities</div>
        </div>
        <div className="card metric-card">
          <span className="metric-label">Edges</span>
          <strong className="metric-value">{overview?.edges ?? "—"}</strong>
          <div className="metric-sub">Semantic Relations</div>
        </div>
        <div className="card metric-card">
          <span className="metric-label">Backend</span>
          <strong className="metric-value" style={{ fontSize: '1.2rem' }}>v{overview?.version ?? "—"}</strong>
          <div className="metric-sub">System Version</div>
        </div>
      </div>

      <div className="actions" style={{ justifyContent: 'flex-end' }}>
        <button className="btn ghost" disabled={loading} onClick={() => void refreshOverview()}>
          {loading ? "Refreshing..." : "Refresh Graph Overview"}
        </button>
      </div>

      {error ? <p className="error">{error}</p> : null}

      <div className="grid-two">
        <div className="card stack">
          <h3>Node Labels</h3>
          <div className="table-wrap">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Label</th>
                  <th>Count</th>
                </tr>
              </thead>
              <tbody>
                {(overview?.node_labels ?? []).map((row) => (
                  <tr key={row.name}>
                    <td>{row.name}</td>
                    <td>{row.count}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

        <div className="card stack">
          <div className="section-header">
            <h3>Relationships</h3>
            <label className="select-wrap">
              <span className="sr-only">Relationship filter</span>
              <select
                value={selectedRelationshipType}
                onChange={(event) => void onRelationshipChange(event.target.value)}
              >
                <option value="">All relationship types</option>
                {(overview?.relationship_types ?? []).map((row) => (
                  <option key={row.name} value={row.name}>
                    {row.name} ({row.count})
                  </option>
                ))}
              </select>
            </label>
          </div>

          <div className="table-wrap">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Type</th>
                  <th>Count</th>
                </tr>
              </thead>
              <tbody>
                {(overview?.relationship_types ?? []).map((row) => (
                  <tr key={row.name}>
                    <td>{row.name}</td>
                    <td>{row.count}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </div>

      <div className="card stack">
        <h3>Entities</h3>
        <div className="table-wrap">
          <table className="data-table">
            <thead>
              <tr>
                <th>Entity</th>
                <th>Kind</th>
                <th>Aliases</th>
                <th>Mentions</th>
                <th>Source Run</th>
              </tr>
            </thead>
            <tbody>
              {(overview?.entities ?? []).map((entity) => (
                <tr key={entity.node_id}>
                  <td>
                    <div className="cell-title">{entity.display_name}</div>
                    <div className="cell-subtle">{entity.node_id}</div>
                  </td>
                  <td>{entity.entity_kind}</td>
                  <td>{entity.alias_count}</td>
                  <td>{entity.mention_count}</td>
                  <td>{entity.source_run_id ?? "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      <div className="card stack">
        <h3>Graph Relationship Data</h3>
        <p className="muted">
          {selectedRelationshipType 
            ? `Showing live rows for ${selectedRelationshipType}.`
            : "Showing live rows across all relationship types."}
        </p>
        <div className="table-wrap">
          <table className="data-table">
            <thead>
              <tr>
                <th>Type</th>
                <th>Source</th>
                <th>Target</th>
                <th>Artifact</th>
                <th>Confidence</th>
              </tr>
            </thead>
            <tbody>
              {relationships.map((row: GraphRelationshipRow, index) => (
                <tr key={`${row.rel_type}-${row.source_id}-${row.target_id}-${index}`}>
                  <td>{row.rel_type}</td>
                  <td>
                    <div className="cell-title">{row.source_display}</div>
                    <div className="cell-subtle">
                      {row.source_labels.join(", ")} · {row.source_id}
                    </div>
                  </td>
                  <td>
                    <div className="cell-title">{row.target_display}</div>
                    <div className="cell-subtle">
                      {row.target_labels.join(", ")} · {row.target_id}
                    </div>
                  </td>
                  <td>{row.artifact_id ?? "—"}</td>
                  <td>{typeof row.confidence === "number" ? row.confidence.toFixed(2) : "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </section>
  );
}
