"use client";

import { useState } from "react";

import type { AgentRunResponse } from "@/lib/types";

const commandOptions = [
  "pipeline",
  "collect",
  "extract",
  "dedup",
  "graph-insert",
  "quality"
] as const;

export default function AgentsPage() {
  const [runId, setRunId] = useState("");
  const [maxItems, setMaxItems] = useState<number>(50);
  const [usernames, setUsernames] = useState("nasa");
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<AgentRunResponse | null>(null);
  const [error, setError] = useState("");

  async function runCommand(command: (typeof commandOptions)[number]) {
    setLoading(true);
    setError("");
    setResult(null);
    try {
      const res = await fetch("/api/agent-run", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          command,
          runId: runId || undefined,
          maxItems: command === "collect" || command === "pipeline" ? maxItems : undefined,
          usernames:
            command === "collect" || command === "pipeline"
              ? usernames
                  .split(",")
                  .map((x) => x.trim())
                  .filter(Boolean)
              : undefined
        })
      });
      const data = (await res.json()) as AgentRunResponse & { error?: string };
      if (!res.ok) {
        throw new Error(data.error || data.stderr || "Agent run failed");
      }
      setResult(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unknown error");
    } finally {
      setLoading(false);
    }
  }

  return (
    <section>
      <h2>Run Agents</h2>
      <p className="muted">Run the whole pipeline or individual stages from UI.</p>

      <div className="card stack">
        <label>
          Run ID (optional for collect/pipeline)
          <input value={runId} onChange={(e) => setRunId(e.target.value)} />
        </label>
        <label>
          Max Items
          <input type="number" value={maxItems} onChange={(e) => setMaxItems(Number(e.target.value || 0))} />
        </label>
        <label>
          Usernames (comma separated)
          <input value={usernames} onChange={(e) => setUsernames(e.target.value)} />
        </label>
        <div className="actions">
          {commandOptions.map((cmd) => (
            <button key={cmd} className="btn" disabled={loading} onClick={() => runCommand(cmd)}>
              {cmd}
            </button>
          ))}
        </div>
      </div>

      {error ? <p className="error">{error}</p> : null}

      {result ? (
        <div className="card">
          <h3>Result: {result.command}</h3>
          <p>Exit code: {result.exitCode}</p>
          <h4>stdout</h4>
          <pre>{result.stdout || "-"}</pre>
          <h4>stderr</h4>
          <pre>{result.stderr || "-"}</pre>
        </div>
      ) : null}
    </section>
  );
}
