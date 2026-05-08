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
        body: JSON.stringify({ text: question, max_results: 5 })
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
            <p className="muted">query_id: {result.query_id || "-"}</p>
            <p className="muted">latency: {result.latency_ms} ms</p>
          </div>
          <div className="card">
            <h3>Cypher</h3>
            <pre>{result.cypher || "-"}</pre>
          </div>
          <div className="card">
            <h3>Citations ({result.citations.length})</h3>
            <pre>{JSON.stringify(result.citations, null, 2)}</pre>
          </div>
        </div>
      ) : null}
    </section>
  );
}
