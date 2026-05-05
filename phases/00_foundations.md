# Phase 0 — Foundations

**Maps to:** [architecture.md](../architecture.md) §6 Phase 0, §1 Vision and scope, §5 Technology (packaging), [requirement.md](../requirement.md) (engineering standards).

> **Layout:** Shared code lives **directly under** [`src/`](../src/) — there is **no** `instagram_osint_kg/` package directory. Top-level: [`config.py`](../src/config.py), [`logging_context.py`](../src/logging_context.py), [`schemas/`](../src/schemas/), [`cli/`](../src/cli/) (dev `python -m cli`). **Pipeline agents** live under [`agents/`](../src/agents/) (`agents.collection`, …).

## Objective

Establish a reproducible project skeleton, configuration, **fixture dataset**, and **provenance schema** so later phases can run in CI **without live Instagram**.

## Prerequisites

- None (first phase).

## Local Python environment (required for checks)

Use a **dedicated virtual environment** so installs, tests, and the dev CLI do not mix with the system Python.

```bash
cd /path/to/Instagram_OSINT_Knowledge_Graph_Agent
python3.10 -m venv tf-env-310
source tf-env-310/bin/activate    # Windows: tf-env-310\Scripts\activate
python -m pip install -U pip
python -m pip install -e ".[dev]"
```

Always run **pytest** (and optional **`python -m cli`**) only **after** `source tf-env-310/bin/activate`. If `pytest` or imports fail, you are usually on the wrong interpreter (check with `which python`).

## Deliverables (checklist)

| # | Deliverable | Status |
|---|-------------|--------|
| 1 | `pyproject.toml` with Python **3.10+**, `pydantic` / `pydantic-settings`, `py-modules` + `packages.find` for flat `src/` | Done |
| 2 | `src/` shared + `src/agents/` for stages (`collection/` … `query/` under `agents/`) — **no** `instagram_osint_kg/` | Done |
| 3 | [`Settings`](../src/config.py) with `DATA_DIR`, `LOG_LEVEL`; **no secrets** in repo | Done |
| 4 | [`.env.example`](../.env.example) | Done |
| 5 | [`fixtures/raw_artifacts.json`](../fixtures/raw_artifacts.json) | Done |
| 6 | [`ProvenanceV1`](../src/schemas/provenance.py) + `provenance_from_raw_artifact()` | Done |
| 7 | CI: [`.github/workflows/ci.yml`](../.github/workflows/ci.yml) | Done |
| 8 | [README.md](../README.md) | Done |
| 9 | Dev CLI: `python -m cli validate-fixtures` / `show-config` / `--version` ([architecture.md](../architecture.md) §2) | Done |
| 10 | LangGraph (**one** `StateGraph`) | **Not in Phase 0** — linear slice in [Phase 4](04_graph_insertion.md#langgraph-single-graph-phase-4); **quality loop** on the **same** graph in [Phase 5](05_quality_checking.md); Query in **Phase 6** via **API** ([architecture.md](../architecture.md) §2.4) |
| 11 | **HTTP API** for frontend | **Later phase** |

## Phase 0 implementation log (follow-along)

- [x] **Layout:** [requirement.md](../requirement.md) §2.1 — `Settings` only in `config.py`; `RawArtifact` / `ProvenanceV1` under `schemas/`; stage placeholders under `agents/<stage>/`.
- [x] **Fixtures:** `fixtures/raw_artifacts.json` validates as `RawArtifact`.
- [x] **Provenance keys** on `ProvenanceV1`; tests in `tests/test_phase0_foundations.py`.
- [x] **`new_run_id()`** in `logging_context.py`.
- [x] **Ruff + pytest** green in CI.
- [ ] **You:** fresh clone → venv → `pip install -e ".[dev]"` → `ruff check src tests` → `pytest`.

## Graph-first proof path (optional teaching order)

See [architecture.md](../architecture.md) §5.2 Path A.

## Implementation tasks

1. Layout: `src/`, `tests/`, `fixtures/`, `data/` (gitignored).
2. **run_id:** `logging_context.new_run_id()`.
3. **RawArtifact** in [`src/schemas/raw_artifact.py`](../src/schemas/raw_artifact.py); validate via `python -m cli validate-fixtures` and tests.
4. `.gitignore` covers `.env`, `__pycache__`, local DB files.

## Data contracts (freeze for downstream)

- **run_id**: string UUID per pipeline execution.
- **Provenance** fields on persisted records (schema in place; values filled in later phases).

## Acceptance criteria

- Fresh clone: `pip install -e ".[dev]"` succeeds; `pytest` runs.
- Fixture loads without network; tests assert provenance keys.
- No credentials committed; `.env.example` only.

## Out of scope

- Live Instagram collection, Neo4j deployment, LLM keys required for CI.

## Next phase

→ [01_collection.md](01_collection.md)
