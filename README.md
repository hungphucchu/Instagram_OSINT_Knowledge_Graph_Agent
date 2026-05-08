# Instagram OSINT Knowledge Graph Agent

A six-agent ingest pipeline plus a Graph-RAG HTTP API that turns public
Instagram posts into a Neo4j knowledge graph and answers natural-language
questions with grounded, cited evidence rows. Built for CS 6263 NLP and
Agentic AI (Spring 2026, UTSA).

The system is designed for OSINT analysts who want short, verifiable answers
about who-mentions-who, hashtag co-occurrence, and entity relationships
across a corpus of public Instagram posts — every answer comes back with the
executed Cypher and the rows it was based on, so the user can verify it.

## Tech Stack

- Python 3.11
- **FastAPI + Uvicorn** — HTTP API and browser UI (`src/myproject/`)
- **Neo4j 5** — graph store (Docker compose)
- **OpenAI-compatible LLMs** — Qwen3-8B (query) and Llama-3.1-8B (extraction)
  via the UTSA-hosted endpoints
- **LangGraph** — orchestrates the ingest pipeline
- **Pydantic / pydantic-settings** — typed configuration and validation
- **Docker + Docker Compose** — single-command deploy
- **Pytest, Ruff, Black, Mypy, Locust, pip-audit** — quality + load tooling
- **Next.js + React + TypeScript** (`web/`) — optional richer demo UI;
  not required for grading.

## Quick Start

The reviewer will run exactly these commands. They work on a fresh clone with no
extra setup.

```bash
git clone https://github.com/[your-org]/[your-repo].git
cd [your-repo]
cp .env.example .env
# Edit .env and set QUERY_LLM_API_KEY (only required key for the happy path).
# NEO4J_PASSWORD is already set to a working default in .env.example.
docker compose up
```

Wait for all services to report healthy.

Service URLs:

- Frontend (Next.js UI): <http://localhost:3000>
- Backend API (FastAPI): <http://localhost:8080>
- Neo4j Browser: <http://localhost:7474>

Estimated time from `docker compose up` to a running app: **under 10 minutes**
on a clean machine.

`docker compose up` starts the app and Neo4j, but it does **not** auto-ingest
sample data. To fill the graph with the bundled fixture after startup, run one
of these:

```bash
# HTTP API
curl -X POST http://127.0.0.1:8080/api/pipeline/sample

# Inside the app container
docker compose exec app python -m myproject.pipeline --sample
```

Then confirm the graph has data:

```bash
curl http://127.0.0.1:8080/api/stats
```

Step-by-step Docker flow from a fresh start:

```bash
# 1. Build and start the full stack (backend, Neo4j, and Next.js UI)
docker compose up --build -d

# 2. Confirm the backend is healthy
curl -fsS http://127.0.0.1:8080/health

# 3. Open the frontend UI
# http://localhost:3000

# 4. Load the bundled sample fixture into the graph
curl -fsS -X POST http://127.0.0.1:8080/api/pipeline/sample

# 5. Verify the graph now has data
curl -fsS http://127.0.0.1:8080/api/stats

# 6. Run one end-to-end query from the API
curl -fsS -H "Content-Type: application/json" \
  -X POST http://127.0.0.1:8080/api/query \
  -d '{"text":"Who appeared together most often?","max_results":5}'
```

Equivalent Next.js UI action:

```text
Open http://localhost:3000/chat
Type: Who appeared together most often?
Click: Ask
```

Optional: rebuild the graph from a larger offline Apify export under
`apify_data/`:

```bash
# 1. Start from a clean local graph + SQLite state
docker compose exec -T app python -m cli local-reset --yes

# 2. Run the full ingest pipeline over a saved Apify export
docker compose exec -T \
  -e COLLECTION_MODE=apify_data \
  -e APIFY_DATA_PATH=/home/app/apify_data/input.json \
  app python -m cli pipeline -v

# 3. Verify the graph counts
curl -fsS http://127.0.0.1:8080/api/stats
```

Notes:

- `myproject.pipeline --sample` only accepts the project's normalized fixture
  schema.
- Raw Apify exports such as `apify_data/input.json` must go through
  `python -m cli pipeline` with `COLLECTION_MODE=apify_data`.
- If you rerun the same Apify export without resetting, unchanged rows may be
  skipped on purpose.

Next.js UI for the manual walkthrough:

`docker compose up --build -d` now starts:

- backend container: `instagram_osint_kg_backend`
- frontend container: `instagram_osint_kg_frontend`

For local frontend-only development outside Docker:

```bash
make web-install
make web-dev
```

Then open <http://localhost:3000>. This is the preferred browser UI for the
manual walkthrough in `docs/STORIES.md`. The Next.js app proxies `/api/*`
requests to the FastAPI backend on <http://127.0.0.1:8080> by default, so keep
the Docker stack running while using the web UI. If your backend lives
elsewhere, set `BACKEND_URL` before starting Next.js.

In short:

- frontend UI: <http://localhost:3000>
- backend API: <http://localhost:8080>

Recommended Next.js pages:

- `/chat` — ask natural-language questions against the graph
- `/graph` — inspect graph stats, entities, and relationship tables
- `/agents` — run pipeline utility actions from the UI

## Run Without Docker

For local backend development, use a fresh Python 3.11 environment:

```bash
python3.11 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
pip install -e .
```

If you want graph features locally, start Neo4j first:

```bash
docker compose up -d neo4j
```

Then start the backend:

```bash
PYTHONPATH=src APP_PORT=8080 python -m myproject.api
```

To fill the graph with the bundled sample fixture in non-Docker mode, run one
of these:

```bash
# HTTP API
curl -X POST http://127.0.0.1:8080/api/pipeline/sample

# Python module entrypoint
PYTHONPATH=src python -m myproject.pipeline --sample
```

Then confirm the graph has data:

```bash
curl http://127.0.0.1:8080/api/stats
```

Then walk the user stories:

```bash
# In a second terminal:
bash scripts/demo.sh
```

## Results

This project reports the following headline metrics, regenerated by
`make reproduce` (see [docs/REPRODUCE.md](docs/REPRODUCE.md)):

| Metric                                       | Value         | Tolerance |
| -------------------------------------------- | ------------- | --------- |
| Sample pipeline raw artifacts ingested       | 2             | exact     |
| Sample pipeline extraction records written   | 2             | exact     |
| Sample pipeline dedup clusters               | 10            | exact     |
| Test coverage on `src/myproject/`            | 0.86          | ± 0.05    |
| `POST /api/query` p95 latency (LLM disabled) | 21 ms         | ± 100 ms  |
| Sustained load throughput                    | ≥ 10 req/s    | rubric    |
| Load-test error rate (60 s window)           | < 5 %         | rubric    |

Source layout: `src/myproject/` (rubric package, the regeneration target);
internal ingest implementation under `src/agents/`; tests under `tests/`.

## Documentation

- [docs/SPEC.md](docs/SPEC.md) — system specification (the source of truth)
- [docs/STORIES.md](docs/STORIES.md) — user stories with manual walkthrough steps
- [docs/usage.md](docs/usage.md) — full usage guide (one section per story)
- [docs/MODEL_CARD.md](docs/MODEL_CARD.md) — model card and limitations
- [docs/REPRODUCE.md](docs/REPRODUCE.md) — reproducibility procedure
- [docs/DATA.md](docs/DATA.md) — datasets and provenance
- [docs/MODELS.md](docs/MODELS.md) — model checkpoints and provenance
- [docs/LOGGING.md](docs/LOGGING.md) — log format and request-trace example
- [docs/benchmarks.md](docs/benchmarks.md) — load-test methodology + numbers
- [docs/diagrams/architecture.svg](docs/diagrams/architecture.svg) — system diagram

## Repository Layout

```
.
├── README.md                       — this file
├── Makefile                        — every target the reviewer invokes
├── Dockerfile                      — multi-stage, runs as non-root
├── docker-compose.yml              — app + neo4j services
├── pyproject.toml                  — pinned deps + tool config
├── requirements.txt                — mirror for pip-audit
├── .env.example                    — copy to .env and fill in
├── CONTRIBUTIONS.md                — team roster + commit shares
├── docs/                           — SPEC, STORIES, MODEL_CARD, REPRODUCE, …
├── grading/                        — manifest, traceability, course grader
├── scripts/                        — preflight, regenerate, demo, …
├── src/
│   ├── myproject/                  — pinned public package (regeneration target)
│   ├── agents/                     — internal ingest + query implementation
│   ├── schemas/                    — Pydantic data contracts
│   ├── cli/                        — `python -m cli ...` developer CLI
│   ├── config.py                   — typed Settings
│   └── logging_context.py          — run-id helper
├── tests/
│   ├── unit/                       — one test per myproject module
│   ├── integration/                — HTTP + ingest wiring
│   ├── user_stories/               — pytest @user_story("US-NN") tests
│   ├── edge/                       — empty / very long / non-ASCII inputs
│   └── load/                       — locustfile.py
├── fixtures/                       — synthetic raw artifacts (committed)
├── apify_data/                     — optional offline Apify exports
├── reports/                        — JUnit + coverage + walkthrough
└── web/                            — optional Next.js demo UI
```

## Contributors

See [CONTRIBUTIONS.md](CONTRIBUTIONS.md).

## License

MIT
