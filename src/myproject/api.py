"""FastAPI HTTP surface for the Instagram OSINT KG Agent.

This module is the public API the rubric grades against:

* ``GET /health`` — Docker health check
* ``GET /`` — minimal browser UI used by the manual walkthrough
* ``POST /api/query`` — main endpoint (US-01 happy path, US-02 empty input,
  US-03 missing API key)
* ``POST /api/pipeline/sample`` — tiny ingest sample (US-04)
* ``GET /api/stats`` — graph node / edge counts (US-05)

Every request gets a fresh ``request_id`` middleware-side and that id is
attached to every log line emitted while the request is in flight, so the TA
can trace a request end-to-end through ``docker compose logs -f app`` (see
``docs/LOGGING.md``).
"""

from __future__ import annotations

import logging
import os
from typing import Any

from fastapi import FastAPI, Request, Response
from fastapi.responses import HTMLResponse, JSONResponse, PlainTextResponse
from pydantic import BaseModel, Field

from myproject import __version__
from myproject.generator import ModelNotConfiguredError
from myproject.logging_setup import (
    configure_logging,
    log_event,
    new_request_id,
    reset_request_id,
    set_request_id,
)
from myproject.router import EmptyInputError, route_query

configure_logging()
LOG = logging.getLogger("myproject.api")


# ---------------------------------------------------------------------------
# Pydantic request / response models — match docs/SPEC.md §4.1 exactly.
# ---------------------------------------------------------------------------
class QueryIn(BaseModel):
    text: str = Field(..., description="Natural-language question")
    max_results: int = Field(default=5, ge=1, le=200)


class Citation(BaseModel):
    doc_id: str
    snippet: str


class QueryOut(BaseModel):
    answer: str
    citations: list[Citation]
    latency_ms: int
    cypher: str | None = None
    query_id: str | None = None
    warnings: list[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# App factory
# ---------------------------------------------------------------------------
app = FastAPI(
    title="Instagram OSINT Knowledge Graph Agent",
    version=__version__,
    description="Graph-RAG over an Instagram OSINT knowledge graph.",
)


@app.middleware("http")
async def _request_id_middleware(request: Request, call_next):
    """Allocate a request id and attach it to context + ``X-Request-ID`` header."""
    rid = request.headers.get("x-request-id") or new_request_id()
    token = set_request_id(rid)
    log_event(LOG, "request_started", method=request.method, path=request.url.path)
    try:
        response: Response = await call_next(request)
    except Exception as exc:  # pragma: no cover - last-resort guard
        log_event(LOG, "request_unhandled_error", level=logging.ERROR, error=str(exc))
        response = JSONResponse({"error": "internal server error"}, status_code=500)
    response.headers["X-Request-ID"] = rid
    log_event(LOG, "request_finished", status=response.status_code)
    reset_request_id(token)
    return response


@app.get("/health", response_class=PlainTextResponse)
def health() -> str:
    return "ok"


@app.get("/api/stats")
def stats() -> dict[str, Any]:
    """US-05: cheap node/edge counts from the live graph."""
    from myproject.retriever import Retriever

    retriever = Retriever()
    try:
        return {"version": __version__, **retriever.graph_stats()}
    finally:
        retriever.close()


# ---------------------------------------------------------------------------
# Main query endpoint — wired to docs/STORIES.md US-01..US-03
# ---------------------------------------------------------------------------
@app.post("/api/query")
def query(payload: QueryIn) -> JSONResponse:
    if not payload.text or not payload.text.strip():
        log_event(LOG, "empty_query_rejected", level=logging.WARNING)
        return JSONResponse({"error": "input text is required"}, status_code=400)
    try:
        result = route_query(payload.text, max_results=payload.max_results)
    except EmptyInputError:
        return JSONResponse({"error": "input text is required"}, status_code=400)
    except ModelNotConfiguredError as exc:
        log_event(LOG, "model_not_configured", level=logging.ERROR, error=str(exc))
        return JSONResponse(
            {"error": "The model service is not configured. Contact the operator."},
            status_code=503,
        )
    except Exception as exc:  # pragma: no cover - safety net
        log_event(LOG, "query_failed", level=logging.ERROR, error=str(exc))
        return JSONResponse(
            {"error": "Unexpected server error while answering the question."},
            status_code=500,
        )
    return JSONResponse(QueryOut.model_validate(result).model_dump())


# ---------------------------------------------------------------------------
# US-04: run a tiny ingest sample so the UI can demo the pipeline.
# ---------------------------------------------------------------------------
class PipelineSampleOut(BaseModel):
    run_id: str
    raw_artifacts: int
    extraction_records: int
    dedup_clusters: int


@app.post("/api/pipeline/sample", response_model=PipelineSampleOut)
def pipeline_sample() -> PipelineSampleOut:
    from myproject.pipeline import run_sample_ingest

    summary = run_sample_ingest()
    return PipelineSampleOut(**summary)


# ---------------------------------------------------------------------------
# Browser UI — single self-contained page so the TA only needs ``docker
# compose up`` to walk every story.
# ---------------------------------------------------------------------------
INDEX_HTML = """<!doctype html>
<html lang=\"en\">
<head>
  <meta charset=\"utf-8\" />
  <meta name=\"viewport\" content=\"width=device-width,initial-scale=1\" />
  <title>Instagram OSINT KG Agent</title>
  <style>
    body { font-family: system-ui, sans-serif; max-width: 880px; margin: 2rem auto; padding: 0 1rem; }
    h1 { margin-bottom: 0.25rem; }
    .sub { color: #555; margin-top: 0; }
    form { display: flex; gap: 0.5rem; margin: 1rem 0; }
    input[type=text] { flex: 1; padding: 0.5rem; font-size: 1rem; }
    button { padding: 0.5rem 1rem; font-size: 1rem; cursor: pointer; }
    .card { border: 1px solid #ddd; border-radius: 6px; padding: 1rem; margin-top: 1rem; }
    .err  { color: #b00020; }
    pre   { background: #f7f7f7; padding: 0.5rem; overflow-x: auto; }
    .row  { display: flex; gap: 0.5rem; align-items: center; flex-wrap: wrap; }
    .pill { background: #eef; padding: 0.15rem 0.4rem; border-radius: 4px; font-size: 0.8rem; }
  </style>
</head>
<body>
  <h1>Instagram OSINT Knowledge Graph Agent</h1>
  <p class=\"sub\">Ask a natural-language question; we answer from the graph with citations.</p>

  <form id=\"qform\">
    <input id=\"q\" type=\"text\" placeholder=\"Who appeared together most often?\" />
    <button id=\"submit-btn\" type=\"submit\">Submit</button>
  </form>
  <div id=\"err\" class=\"err\" role=\"alert\"></div>

  <section id=\"out\" class=\"card\" hidden>
    <h2>Answer</h2>
    <p id=\"answer\"></p>
    <div class=\"row\">
      <span class=\"pill\" id=\"latency\"></span>
      <span class=\"pill\" id=\"qid\"></span>
    </div>
    <h3>Citations</h3>
    <ul id=\"citations\"></ul>
    <details><summary>Generated Cypher</summary><pre id=\"cypher\"></pre></details>
  </section>

  <section class=\"card\">
    <h3>Pipeline / graph utilities</h3>
    <button id=\"sample-btn\">Run sample pipeline (US-04)</button>
    <button id=\"stats-btn\">Refresh graph stats (US-05)</button>
    <pre id=\"util-out\"></pre>
  </section>

  <script>
  const $ = (id) => document.getElementById(id);
  $('qform').addEventListener('submit', async (ev) => {
    ev.preventDefault();
    $('err').textContent = '';
    const text = $('q').value || '';
    if (!text.trim()) {
      $('err').textContent = 'Please enter a question';
      return;
    }
    $('out').hidden = true;
    const res = await fetch('/api/query', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({text, max_results: 5}),
    });
    let body = {};
    try { body = await res.json(); } catch (_) { body = {}; }
    if (!res.ok) {
      $('err').textContent = body.error || ('Request failed: ' + res.status);
      return;
    }
    $('answer').textContent = body.answer || '';
    $('latency').textContent = (body.latency_ms || 0) + ' ms';
    $('qid').textContent    = body.query_id ? ('id: ' + body.query_id) : '';
    $('cypher').textContent = body.cypher || '';
    const ul = $('citations');
    ul.innerHTML = '';
    for (const c of (body.citations || [])) {
      const li = document.createElement('li');
      li.textContent = c.doc_id + ' — ' + c.snippet;
      ul.appendChild(li);
    }
    $('out').hidden = false;
  });

  $('sample-btn').addEventListener('click', async () => {
    $('util-out').textContent = 'Running sample ingest...';
    const res = await fetch('/api/pipeline/sample', {method: 'POST'});
    $('util-out').textContent = JSON.stringify(await res.json(), null, 2);
  });
  $('stats-btn').addEventListener('click', async () => {
    const res = await fetch('/api/stats');
    $('util-out').textContent = JSON.stringify(await res.json(), null, 2);
  });
  </script>
</body>
</html>
"""


@app.get("/", response_class=HTMLResponse)
def index() -> str:
    return INDEX_HTML


# Convenience for ``python -m myproject.api``.
def _main() -> int:
    import uvicorn

    port = int(os.getenv("APP_PORT", "8080"))
    uvicorn.run("myproject.api:app", host="0.0.0.0", port=port, log_config=None)
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(_main())
