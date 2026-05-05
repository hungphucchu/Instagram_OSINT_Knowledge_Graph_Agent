# Engineering requirements

This document defines how code in this repository should be written, reviewed, and run. It applies to human contributors and to **automation (agents, CI, scripts)**.

---

## 1. Virtual environment and read before you run

### 1.1 Virtual environment — mandatory before every command

**Rule:** You **must** use a **dedicated virtual environment** for this repository. Do **not** install project dependencies into the system Python, and do **not** run project tools with an interpreter that is not the venv’s `python`.

**Applies to all of:** `pip` / `pip install`, `python -m pip`, `pytest`, `python -m pytest`, `python -m cli` (dev smoke CLI), `ruff`, editable installs (`pip install -e .`), and any script or agent step that imports from the flat `src/` modules (`config`, `schemas`, …).

**Required workflow:**

1. Create a venv once (see [`phases/00_foundations.md`](phases/00_foundations.md), e.g. `python3.10 -m venv tf-env-310`).
2. **Activate** it before any install or run (`source tf-env-310/bin/activate` on macOS/Linux; `tf-env-310\Scripts\activate` on Windows).
3. Install dependencies **only** with that venv’s `python -m pip` (e.g. `python -m pip install -e ".[dev]"`).
4. Run **every** subsequent command in an **activated** shell, **or** call the venv’s `python` by **absolute path** (no ambiguity).

**Verify before running anything:** `which python` / `where python` must resolve to a path **inside** your venv (e.g. `.../tf-env-310/bin/python`). If it does not, stop and activate (or fix `PATH`).

**CI / automation:** Each job must use an **isolated** environment (e.g. create `python -m venv .venv-ci` in the job, then use **that** `python`/`pip` only). That satisfies this rule; using the runner’s global `python`/`pip` for project installs does **not**.

**Agents and docs:** Any instruction to “run tests” or “run the dev CLI” **must** state venv activation first (or use the venv `python` absolute path). Do not assume `pytest` on `PATH` is tied to this project.

### 1.2 Read before you run or change code

**Rule:** Before executing project code or submitting a non-trivial change, **read this file** and the **relevant phase spec** (see [`phases/`](phases/)), and skim [`architecture.md`](architecture.md) for boundaries (provenance, compliance, agent stages).

**Intent:** Avoid one-off hacks that violate provenance, safety (e.g. mutating Cypher), or layering. If a task conflicts with this document, **resolve the conflict explicitly** (issue, comment, or doc update) instead of silently ignoring it.

**Minimal checklist before a run:**

1. [ ] **Virtualenv active** (or CI isolated venv) — **§1.1** satisfied; `which python` is inside the project venv.
2. [ ] `.env` present for live APIs; never commit secrets.
3. [ ] Change aligns with **§2–§6** below (including **§2.1** layout) for code you are touching.
4. [ ] Tests or dry-run path identified for the change.

---

## 2. Clean code

- **Names:** Reveal intent; avoid abbreviations unless domain-standard (`NER`, `Cypher`).
- **Functions:** Short, single purpose; prefer many small functions over long procedures.
- **Comments:** Explain *why*, not *what*, unless the algorithm is non-obvious.
- **Formatting:** One style consistently (e.g. Ruff/Black if adopted); no unrelated reformatting in the same commit as a feature fix.
- **Dead code:** Remove unused imports, variables, and commented-out blocks; use version control for history.
- **Errors:** Fail with clear exceptions or structured errors; log **run_id** where the pipeline already defines it.
- **Magic values:** Pull thresholds, URLs, and limits into config or named constants.

### 2.1 One class per file and a discoverable layout

**Intent:** Keep the tree easy to navigate: open a file and see **one main abstraction**, not unrelated types mixed together.

- **Agents, stores, adapters, and long-lived clients:** **One primary public `class` per module** (e.g. `CollectionAgent` in `agents/collection/agent.py`, `RawArtifactStore` in `agents/collection/store.py`). If you need a second major type, **add another module** in the same agent subpackage instead of stacking classes in one file.
- **Nested types:** Inner/helper classes that exist only to support the primary class are fine **inside** that class’s definition.
- **Data-only bundles:** For a single pipeline stage, several small Pydantic/dataclass **config or DTO** types may live in that stage’s `models.py` (one **logical** “models” slice). Do **not** put a large agent/store class in `models.py`, and do **not** merge two stages into one file.
- **Shared schemas:** Cross-cutting JSON shapes and reports belong under `schemas/` (or clearly named modules), not copied into random agent files.
- **Anti-pattern:** “God files” that combine unrelated agents, stores, HTTP clients, and one-off scripts. Prefer **thin modules** and **explicit imports** so dependency direction stays obvious.

**New code** should follow this layout from the first commit; **legacy** modules may still deviate—when you touch them, split or move types toward this rule rather than adding more unrelated classes to the same file.

---

## 3. SOLID principles

Map SOLID to this pipeline (agents, stores, graph, LLM clients):

| Principle | Expectation in this project |
|-----------|-----------------------------|
| **S**ingle responsibility | Each agent module owns one stage (collection, extraction, dedup, graph, quality, query). Adapters (`SourceAdapter`, graph backend) do not embed unrelated business logic. Pair with **§2.1**: one primary class per file for agents/stores/adapters. |
| **O**pen/closed | Extend via new adapters or new rule packs, not by editing core orchestration for every variant. |
| **L**iskov substitution | Implementations of the same interface (e.g. fixture vs live collector) must be drop-in for the orchestrator without special cases at call sites. |
| **I**nterface segregation | Small protocols / ABCs: “read artifacts”, “write graph”, “complete chat” — avoid one giant “do everything” interface. |
| **D**ependency inversion | High-level pipeline depends on abstractions (interfaces, config-injected clients), not concrete Neo4j/HTTP details inside every agent. |

---

## 4. Concurrency and multi-threaded serving

**Batch pipeline:** The six-agent flow may run **sequentially** per `run_id` for clarity and reproducibility. Use **thread pools or `async`** only where there is a measured need (e.g. I/O-bound collection or parallel embedding batches), and document shared-state rules.

**Primary delivery (target):** A **backend HTTP API** for the frontend, as described in [architecture.md](architecture.md) §2. Implement pipeline and Graph RAG behind **service functions or use-cases** that both the **API** and optional **dev CLI** call—do not embed core logic only in CLI handlers.

**If you add an HTTP or RPC service:**

- Prefer **explicit thread/process pool** or **async** with clear bounds; cap workers and queue depth.
- **No shared mutable graph or DB connection** across threads without proper pooling or locking; use connection pools provided by the driver.
- **Idempotent** handlers where possible; timeouts on outbound LLM and DB calls.
- **Health checks** and graceful shutdown (stop accepting work, drain, close pools).
- Document expected **QPS**, thread model, and failure modes in code or a short ops note.

**Safety:** LLM and graph clients used from multiple threads must be either immutable wrappers around thread-safe SDKs or one client per worker per vendor documentation.

---

## 5. Security and compliance

- Public-data and fixture-only defaults per [`architecture.md`](architecture.md); no bypass of access controls.
- Secrets only in environment or secret stores; **never** in the knowledge graph as plain text credentials.
- Query path remains **read-only** at execution time (verifier); log queries for audit.

---

## 6. Testing and quality gates

- **Unit tests** per non-trivial module; **integration** tests on fixtures (no live Instagram in CI).
- Run **`python -m pytest`** only **after §1.1** (venv active or CI isolated env) before merge or hand-off.
- Prefer deterministic tests; mock external HTTP for LLM tests when not running contract tests against UTSA endpoints.

---

## 7. Operations and observability

- Structured logging with **run_id** (and **query_id** for QueryAgent when implemented).
- Configurable timeouts and retries for external APIs (see existing LLM client patterns).
- Pin dependencies in `pyproject.toml` for reproducible builds.

---

## 8. When this document changes

Updates here should reflect real practice: if the team adopts a formatter, a server framework, or changes the threading model, **edit this file in the same PR** so the next reader (human or agent) still has a single source of truth.

---

## 9. Repository compliance snapshot (code vs this doc)

The [`phases/`](phases/) markdown files are the **implementation contract** for what “done” means per milestone; keep them aligned with [architecture.md](architecture.md) when the design evolves.

| Topic | Current repo status |
|-------|---------------------|
| §1.1 Virtualenv | Documented as **mandatory** before every `pip` / `pytest` / `python -m …`; see [`phases/00_foundations.md`](phases/00_foundations.md). |
| Phase 0 complete | **Flat `src/`** for shared code + [`agents/`](src/agents/) for pipeline stages (no `instagram_osint_kg/` dir): [`config.py`](src/config.py), [`schemas/`](src/schemas/), [`cli/`](src/cli/), [`fixtures/`](fixtures/), CI. |
| Phase 1 collection | **Implemented (baseline)** — [`CollectionAgent`](src/agents/collection/collection_agent.py), [`RawArtifactStore`](src/agents/collection/raw_artifact_store.py), fixture + Apify adapters, and Apify request cache; see [`phases/01_collection.md`](phases/01_collection.md). |
| Phase 2 extraction | **Implemented (baseline)** — heuristic + LLM-ready extractor path, [`ExtractionStore`](src/agents/extraction/extraction_store.py), and CLI `extract --run-id ...`; see [`phases/02_extraction.md`](phases/02_extraction.md). |
| Phase 3 dedup | **Implemented (baseline)** — deterministic dedup pipeline with fuzzy + char n-gram gate, clustering, report + audit persistence, and CLI `dedup --run-id ...`; see [`phases/03_deduplication.md`](phases/03_deduplication.md). |
| Phase 4 graph + LangGraph | **Implemented (linear path)** — Neo4j insertion in [`agents/graph_insertion/`](../src/agents/graph_insertion/); LangGraph `collect → extract → dedup → graph_insert` in [`agents/pipeline/`](../src/agents/pipeline/) with CLI `python -m cli pipeline`. Phase 5 adds the quality loop on the same graph. |
| Phase 5 quality | **Implemented (baseline)** — deterministic integrity gate + LLM judge, `QualityReport` + optional quarantine JSON, LangGraph `quality` after `graph_insert` with retry to `extract` or `dedup`; CLI `quality` / extended `pipeline`; see [`phases/05_quality_checking.md`](phases/05_quality_checking.md). |
| Phase 6 query | **Implemented (baseline)** — `QueryAgent` with read-only Cypher verifier, bounded LIMIT enforcement, Neo4j execution, evidence-first answer envelope, and CLI `query`; see [`phases/06_query_answering.md`](phases/06_query_answering.md). |
| §2 Clean code / layout | Magic values live in [`Settings`](src/config.py); dev CLI uses explicit logging. **§2.1** (one primary class per file for agents/stores; stage-scoped `models.py` for DTOs) is the target for **new** code. |
| §3 SOLID (full pipeline) | **Partial.** LLM clients and stores are modular; **Neo4j adapter**, **QualityAgent**, **QueryAgent**, and optional **Apify**/**Instaloader** adapters are not complete — see [`phases/`](phases/). |
| §4 Concurrency / serving | **HTTP API not implemented yet**; when added, follow §4 pool/async and edge limits. Until then, optional dev CLI and tests are single-threaded by default. |
| §5 Security | Keys via `.env` only; NL→Cypher execution must stay read-only when QueryAgent lands (verifier design in architecture / Phase 6). |
| §6 Tests | Phase 0 fixture/schema tests; **LangGraph fixture pipeline** test in [`tests/test_langgraph_pipeline.py`](../tests/test_langgraph_pipeline.py). No live Instagram or live LLM required in CI. |
| §7 Observability | `run_id` on collection/extraction/pipeline; extend with `query_id` when QueryAgent exists. |
| §7 Pins / style | Upper-bound pins in [`pyproject.toml`](pyproject.toml); Ruff — run `ruff check src tests`. |

Re-audit this table when adding agents, a server, Neo4j-backed insertion, or graph query execution.

---

*Complements [`architecture.md`](architecture.md) (system design) and [`phases/`](phases/) (implementation order).*
