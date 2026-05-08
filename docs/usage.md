# Usage Guide

> Every story listed in `docs/STORIES.md` has a corresponding section here.
> Each section below matches the current Next.js walkthrough flow.
>
> Demo capture: [docs/assets/demo.gif](assets/demo.gif)

## Running the sample ingest (US-01)

From the UI:

1. Visit <http://localhost:3000/agents>.
2. Confirm the page title reads **Pipeline Console**.
3. Click **Run Sample Ingest**.
4. The **Latest Sample Ingest** card appears as a table showing the **Run ID**, 
   **Raw Artifacts**, **Extraction Records**, and **Dedup Clusters**.
5. Optionally click **Run Full Ingest** to run the configured end-to-end ingest pipeline.
   The UI then shows a **Latest Full Ingest** card with per-phase statuses.

From the terminal:

```bash
make download-data            # Ensure fixtures are available
PYTHONPATH=src python -m myproject.pipeline --sample
```

## Inspecting graph stats (US-02)

From the UI, visit <http://localhost:3000/graph> and click
**Refresh Graph Overview**. The page then shows:

1. metric cards for Nodes/Edges/Backend,
2. a **Node Labels** count table,
3. a **Relationships** count table with relationship-type dropdown filter,
4. an **Entities** table, and
5. a **Graph Relationship Data** table.

Core count data is also available via:

```bash
curl -s http://localhost:8080/api/stats | jq
```

The output is `{"version": "...", "nodes": int, "edges": int}`.

Richer graph explorer data comes from:

```bash
curl -s "http://localhost:8080/api/graph/overview" | jq
```

## Submitting a question (US-03)

To ask a question:

1. Visit <http://localhost:3000/chat>.
2. Type your question in the **Question** field.
3. Click **Ask Graph**.
4. The Answer, query id, latency, Citations, and Cypher cards appear below the
   form.

Tips:

* Phrase questions as full sentences ("Who appeared together most often?"
  is better than "co-appearance").
* The `max_results` parameter (default 5) is exposed as a JSON field on the
  API; the UI uses the default. Set `"max_results": 20` in the request
  body to see more rows.
* You can also call the API directly:

  ```bash
  curl -s http://localhost:8080/api/query \
    -H 'Content-Type: application/json' \
    -d '{"text":"Who appeared together most often?","max_results":5}' | jq
  ```

## Empty input handling (US-04)

If you click **Ask Graph** with an empty question, the Next.js page displays
the backend error inline. The request to `POST /api/query` returns HTTP 400 with body
`{"error": "input text is required"}`. No LLM tokens are spent.

## Configuration troubleshooting (US-05)

If the `/chat` page shows "The model service is not configured. Contact the
operator.", the LLM credential is missing:

```bash
# Stop the app
docker compose down
# Edit .env and restore the credential
echo "QUERY_LLM_API_KEY=<your token>" >> .env
# Restart
docker compose up
```

While the credential is missing, every `/api/query` returns HTTP 503.
`/health` and `/api/stats` remain available because they do not call the LLM.

## Bringing the system up and down

```bash
# First-time / fresh clone
cp .env.example .env
# Edit .env and set QUERY_LLM_API_KEY (and NEO4J_PASSWORD if you want to)
docker compose up

# Stop all services
docker compose down

# Wipe Neo4j volumes (destructive)
docker compose down -v
```

## Headless / CI checks

```bash
make install-dev          # local dev install
make lint                 # ruff + black --check + mypy
make test                 # unit + integration + user_stories + edge
make loadtest             # 60s sustained load against the running app
make demo                 # exercises every story end-to-end via curl
make preflight            # everything the reviewer runs in Phase 1 of grading
```
