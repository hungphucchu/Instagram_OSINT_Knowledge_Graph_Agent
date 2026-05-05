"use client";

import { FormEvent, useState } from "react";

import type { QueryApiResponse } from "@/lib/types";

export default function ChatPage() {
  const [question, setQuestion] = useState("Who appeared together most often?");
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<QueryApiResponse | null>(null);
  const [error, setError] = useState<string>("");

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setLoading(true);
    setError("");
    setResult(null);
    try {
      const res = await fetch("/api/query", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ question, showCypher: true })
      });
      const data = await res.json();
      if (!res.ok) {
        throw new Error(data.error || "Query failed");
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
      <h2>Chat Interface</h2>
      <p className="muted">Ask natural language questions about your Instagram knowledge graph.</p>
      <form className="card stack" onSubmit={onSubmit}>
        <label htmlFor="question">Question</label>
        <textarea id="question" value={question} onChange={(e) => setQuestion(e.target.value)} rows={3} />
        <button className="btn" disabled={loading} type="submit">
          {loading ? "Running..." : "Ask Graph"}
        </button>
      </form>

      {error ? <p className="error">{error}</p> : null}

      {result ? (
        <div className="stack">
          <div className="card">
            <h3>Answer</h3>
            <p>{result.answer}</p>
            <p className="muted">query_id: {result.queryId}</p>
          </div>
          <div className="card">
            <h3>Cypher</h3>
            <pre>{result.cypher || "-"}</pre>
          </div>
          <div className="card">
            <h3>Evidence ({result.evidenceRows})</h3>
            <pre>{JSON.stringify(result.evidence, null, 2)}</pre>
          </div>
        </div>
      ) : null}
    </section>
  );
}
