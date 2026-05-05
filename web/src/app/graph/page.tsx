"use client";

import { FormEvent, useState } from "react";

import { SimpleGraph } from "@/components/simple-graph";
import type { QueryApiResponse } from "@/lib/types";

export default function GraphPage() {
  const [question, setQuestion] = useState("top co-appears");
  const [result, setResult] = useState<QueryApiResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  async function loadGraph(e: FormEvent) {
    e.preventDefault();
    setLoading(true);
    setError("");
    try {
      const res = await fetch("/api/query", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ question, showCypher: true })
      });
      const data = await res.json();
      if (!res.ok) {
        throw new Error(data.error || "Failed to load graph evidence");
      }
      setResult(data as QueryApiResponse);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unknown error");
    } finally {
      setLoading(false);
    }
  }

  return (
    <section>
      <h2>Graph Display</h2>
      <p className="muted">Visualize relationship-style evidence for a bigger picture view.</p>
      <form className="card stack" onSubmit={loadGraph}>
        <label htmlFor="graph-question">Question for graph projection</label>
        <input id="graph-question" value={question} onChange={(e) => setQuestion(e.target.value)} />
        <button className="btn" disabled={loading} type="submit">
          {loading ? "Loading..." : "Render Graph"}
        </button>
      </form>
      {error ? <p className="error">{error}</p> : null}
      <div className="card">
        <SimpleGraph rows={result?.evidence || []} />
      </div>
      {result ? (
        <div className="card">
          <h3>Evidence Preview</h3>
          <pre>{JSON.stringify(result.evidence.slice(0, 8), null, 2)}</pre>
        </div>
      ) : null}
    </section>
  );
}
