"use client";

import { useState } from "react";

import type {
  PipelineFullJobStatusResponse,
  PipelineFullJobSubmitResponse,
  PipelineFullResponse,
  PipelineSampleResponse
} from "@/lib/types";

type ActionState = "sample" | "full" | null;

type PhaseRow = {
  step: string;
  status: string;
  detail: string;
};

async function readApiPayload(res: Response): Promise<{ json: unknown | null; text: string }> {
  const raw = await res.text();
  try {
    return { json: JSON.parse(raw) as unknown, text: raw };
  } catch {
    return { json: null, text: raw };
  }
}

function extractErrorMessage(
  payload: unknown,
  fallback: string
): string {
  if (payload && typeof payload === "object" && "error" in payload) {
    const maybeError = (payload as { error?: unknown }).error;
    if (typeof maybeError === "string" && maybeError.trim()) {
      return maybeError;
    }
  }
  return fallback;
}

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
  const [fullLogs, setFullLogs] = useState<string[]>([]);
  const [fullRunState, setFullRunState] = useState<"idle" | "running" | "done" | "failed">("idle");

  function appendFullLog(message: string) {
    const stamp = new Date().toLocaleTimeString();
    setFullLogs((prev) => [...prev, `[${stamp}] ${message}`]);
  }

  async function runSample() {
    setLoadingAction("sample");
    setError("");
    try {
      const res = await fetch("/api/pipeline/sample", { method: "POST" });
      const { json, text } = await readApiPayload(res);
      if (!res.ok) {
        const fallback = text.trim() || `Failed to run sample ingest (HTTP ${res.status})`;
        throw new Error(extractErrorMessage(json, fallback));
      }
      setSample((json ?? {}) as PipelineSampleResponse);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unknown error");
    } finally {
      setLoadingAction(null);
    }
  }

  async function runFullIngest() {
    setLoadingAction("full");
    setError("");
    setFullRunState("running");
    setFullLogs([]);
    appendFullLog("Full ingest requested from Pipeline Console.");
    appendFullLog("Submitting job to /api/pipeline/full/submit.");
    let elapsed = 0;
    const stageHints = [
      "Collection phase running...",
      "Extraction phase running...",
      "Deduplication phase running...",
      "Graph insertion phase running...",
      "Quality gate phase running..."
    ];
    let stageIndex = 0;
    try {
      const submitRes = await fetch("/api/pipeline/full/submit", { method: "POST" });
      const { json: submitJson, text: submitText } = await readApiPayload(submitRes);
      if (!submitRes.ok) {
        const fallback = submitText.trim() || `Failed to submit full ingest (HTTP ${submitRes.status})`;
        throw new Error(extractErrorMessage(submitJson, fallback));
      }
      const submitted = (submitJson ?? {}) as PipelineFullJobSubmitResponse;
      if (!submitted.job_id) {
        throw new Error("Backend did not return a job_id for full ingest.");
      }
      appendFullLog(`Job queued: ${submitted.job_id}`);

      // Poll status endpoint until terminal state.
      let pollCount = 0;
      while (true) {
        await new Promise((resolve) => window.setTimeout(resolve, 2000));
        elapsed += 2;
        pollCount += 1;

        if (stageIndex < stageHints.length && elapsed >= (stageIndex + 1) * 6) {
          appendFullLog(stageHints[stageIndex]);
          stageIndex += 1;
        } else if (pollCount % 3 === 0) {
          appendFullLog(`Still running... ${elapsed}s elapsed.`);
        }

        const statusRes = await fetch(`/api/pipeline/full/jobs/${submitted.job_id}`, { cache: "no-store" });
        const { json: statusJson, text: statusText } = await readApiPayload(statusRes);
        if (!statusRes.ok) {
          const fallback = statusText.trim() || `Failed to read full ingest status (HTTP ${statusRes.status})`;
          throw new Error(extractErrorMessage(statusJson, fallback));
        }
        const job = (statusJson ?? {}) as PipelineFullJobStatusResponse;
        if (job.status === "queued" && pollCount % 2 === 0) {
          appendFullLog("Job still queued.");
          continue;
        }
        if (job.status === "running" && pollCount % 2 === 0) {
          appendFullLog("Job running on backend.");
          continue;
        }
        if (job.status === "failed") {
          throw new Error(job.error || "Full ingest job failed.");
        }
        if (job.status !== "completed") {
          continue;
        }

        const parsed = (job.result ?? null) as PipelineFullResponse | null;
        if (!parsed) {
          throw new Error("Full ingest completed but no result payload was returned.");
        }
        setFullRun(parsed);
        appendFullLog("Backend reported job completed.");
        appendFullLog(`Run ID: ${parsed.run_id || "unknown"}`);
        appendFullLog(`Last step: ${parsed.last_step ?? "unknown"}`);
        for (const row of [
          summarizePhase("collection", parsed.collection),
          summarizePhase("extraction", parsed.extraction),
          summarizePhase("dedup", parsed.dedup),
          summarizePhase("graph_insert", parsed.graph_insert),
          summarizePhase("quality", parsed.quality)
        ]) {
          appendFullLog(`[${row.step}] status=${row.status}; ${row.detail}`);
        }
        appendFullLog(parsed.succeeded ? "Full ingest completed successfully." : "Full ingest completed with warnings/errors.");
        setFullRunState("done");
        break;
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unknown error");
      appendFullLog(err instanceof Error ? `Full ingest failed: ${err.message}` : "Full ingest failed: unknown error");
      setFullRunState("failed");
    }
    setLoadingAction(null);
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
            <span className="btn-content">
              {loadingAction === "sample" ? <span className="loading-spinner" aria-hidden="true" /> : null}
              {loadingAction === "sample" ? "Running Sample..." : "Run Sample Ingest"}
            </span>
          </button>
          <button className="btn secondary" disabled={loadingAction !== null} onClick={runFullIngest}>
            <span className="btn-content">
              {loadingAction === "full" ? <span className="loading-spinner" aria-hidden="true" /> : null}
              {loadingAction === "full" ? "Running Full Ingest..." : "Run Full Ingest"}
            </span>
          </button>
        </div>
        <p className="muted" style={{ fontSize: '0.85rem' }}>Select a workflow to begin populating the knowledge graph.</p>
      </div>

      {error ? <p className="error">{error}</p> : null}

      {fullRunState !== "idle" ? (
        <div className="card stack">
          <div className="section-header">
            <h3>Full Ingest Run Log</h3>
            <span
              className={`status-pill ${
                fullRunState === "done" ? "ok" : fullRunState === "failed" ? "warn" : ""
              }`}
            >
              {fullRunState === "running"
                ? "Running"
                : fullRunState === "done"
                ? "Completed"
                : "Failed"}
            </span>
          </div>
          <pre className="log-panel">{fullLogs.join("\n") || "No logs yet."}</pre>
        </div>
      ) : null}

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
