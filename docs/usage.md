# Usage Guide

> Every story listed in `docs/STORIES.md` has a corresponding section here.
> The TA verifies this mapping during the Documentation walkthrough.
>
> Demo capture: [docs/assets/demo.gif](assets/demo.gif)

## Submitting a question (US-01)

To ask a question:

1. Visit <http://localhost:8080>.
2. Type your question in the input box.
3. Click **Submit**.
4. The Answer, Latency, Citations, and the Generated Cypher appear below the
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

## Empty input handling (US-02)

If you click **Submit** without typing anything, the UI displays
"Please enter a question" inline and does not call the API. If a script
bypasses the client-side guard and POSTs `{"text": ""}` directly,
`POST /api/query` returns HTTP 400 with body
`{"error": "input text is required"}`. No LLM tokens are spent.

## Configuration troubleshooting (US-03)

If the system shows "The model service is not configured. Contact the
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

## Running the sample ingest (US-04)

From the UI:

1. Visit <http://localhost:8080>.
2. Scroll to the "Pipeline / graph utilities" panel.
3. Click **Run sample pipeline (US-04)**.
4. The panel below the buttons shows a JSON summary of how many raw
   artifacts, extraction records, and dedup clusters the run produced.

From the terminal:

```bash
make download-data            # stage fixtures into data/
PYTHONPATH=src python -m myproject.pipeline --sample
```

## Inspecting graph stats (US-05)

From the UI, click **Refresh graph stats (US-05)**. The same data is
available via:

```bash
curl -s http://localhost:8080/api/stats | jq
```

The output is `{"version": "...", "nodes": int, "edges": int}`.

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
make preflight            # everything the TA runs in Phase 1 of grading
```
