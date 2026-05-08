"use client";

import { useState } from "react";

import type {
  PipelineFullResponse,
  PipelineSampleResponse
} from "@/lib/types";

type ActionState = "sample" | "full" | null;

type PhaseRow = {
  step: string;
  status: string;
  detail: string;
};

function summarizePhase(step: string, payload: Record<string, unknown>): PhaseRow {
  if (step === "collection") {
    return {
      step,
      status: String(payload.status ?? "unknown"),
      detail: `collected=${payload.artifacts_collected ?? 0}, skipped=${payload.artifacts_skipped_unchanged ?? 0}`
    };
  }
  if (step === "extraction") {
    return {
      step,
      status: String(payload.status ?? "unknown"),
      detail: `records_written=${payload.records_written ?? 0}`
    };
  }
  if (step === "dedup") {
    return {
      step,
      status: String(payload.status ?? "unknown"),
      detail: `clusters_written=${payload.clusters_written ?? 0}`
    };
  }
  if (step === "graph_insert") {
    return {
      step,
      status: String(payload.status ?? "unknown"),
      detail: `nodes_created=${payload.nodes_created ?? 0}, relationships_created=${payload.relationships_created ?? 0}`
    };
  }
  return {
    step,
    status: String(payload.status ?? "unknown"),
    detail: `gate_passed=${String(payload.gate_passed ?? false)}`
  };
}

export default function AgentsPage() {
  const [loadingAction, setLoadingAction] = useState<ActionState>(null);
  const [error, setError] = useState("");
  const [sample, setSample] = useState<PipelineSampleResponse | null>(null);
  const [fullRun, setFullRun] = useState<PipelineFullResponse | null>(null);

  async function runSample() {
    setLoadingAction("sample");
    setError("");
    try {
      const res = await fetch("/api/pipeline/sample", { method: "POST" });
      const data = await res.json();
      if (!res.ok) {
        throw new Error(data.error || "Failed to run sample ingest");
      }
      setSample(data as PipelineSampleResponse);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unknown error");
    } finally {
      setLoadingAction(null);
    }
  }

  async function runFullIngest() {
    setLoadingAction("full");
    setError("");
    try {
      const res = await fetch("/api/pipeline/full", { method: "POST" });
      const data = await res.json();
      if (!res.ok) {
        throw new Error(data.error || "Failed to run full ingest");
      }
      setFullRun(data as PipelineFullResponse);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unknown error");
    } finally {
      setLoadingAction(null);
    }
  }

  const phaseRows = fullRun
    ? [
        summarizePhase("collection", fullRun.collection),
        summarizePhase("extraction", fullRun.extraction),
        summarizePhase("dedup", fullRun.dedup),
        summarizePhase("graph_insert", fullRun.graph_insert),
        summarizePhase("quality", fullRun.quality)
      ]
    : [];

  return (
    <section className="stack">
      <div>
        <h2>Pipeline Console</h2>
        <p className="muted">
          Orchestrate automated ingestion workflows to collect, extract, and synchronize Instagram 
          OSINT data within the Knowledge Graph.
        </p>
      </div>

      <div className="card stack" style={{ borderLeft: '4px solid #3b82f6' }}>
        <div className="actions">
          <button className="btn" disabled={loadingAction !== null} onClick={runSample}>
            {loadingAction === "sample" ? "Running Sample..." : "Run Sample Ingest"}
          </button>
          <button className="btn secondary" disabled={loadingAction !== null} onClick={runFullIngest}>
            {loadingAction === "full" ? "Running Full Ingest..." : "Run Full Ingest"}
          </button>
        </div>
        <p className="muted" style={{ fontSize: '0.85rem' }}>Select a workflow to begin populating the knowledge graph.</p>
      </div>

      {error ? <p className="error">{error}</p> : null}

      {sample ? (
        <div className="card stack">
          <h3>Latest Sample Ingest</h3>
          <p className="muted">Results from the deterministic fixture ingest.</p>
          <table className="data-table">
            <tbody>
              <tr>
                <th>Run ID</th>
                <td>{sample.run_id}</td>
              </tr>
              <tr>
                <th>Raw Artifacts</th>
                <td>{sample.raw_artifacts}</td>
              </tr>
              <tr>
                <th>Extraction Records</th>
                <td>{sample.extraction_records}</td>
              </tr>
              <tr>
                <th>Dedup Clusters</th>
                <td>{sample.dedup_clusters}</td>
              </tr>
            </tbody>
          </table>
        </div>
      ) : null}

      {fullRun ? (
        <div className="card stack">
          <div className="section-header">
            <div>
              <h3>Latest Full Ingest</h3>
              <p className="muted">
                Source mode <code>{fullRun.collection_mode}</code> from <code>{fullRun.source_path}</code>
              </p>
            </div>
            <span className={`status-pill ${fullRun.succeeded ? "ok" : "warn"}`}>
              {fullRun.succeeded ? "Succeeded" : "Needs Attention"}
            </span>
          </div>

          <table className="data-table">
            <tbody>
              <tr>
                <th>Run ID</th>
                <td>{fullRun.run_id || "—"}</td>
              </tr>
              <tr>
                <th>Last Step</th>
                <td>{fullRun.last_step ?? "—"}</td>
              </tr>
            </tbody>
          </table>

          <div className="table-wrap">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Pipeline Step</th>
                  <th>Status</th>
                  <th>Detail</th>
                </tr>
              </thead>
              <tbody>
                {phaseRows.map((row) => (
                  <tr key={row.step}>
                    <td>{row.step}</td>
                    <td>{row.status}</td>
                    <td>{row.detail}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      ) : null}
    </section>
  );
}
