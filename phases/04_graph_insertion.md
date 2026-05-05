# Phase 4 — Graph insertion

**Agent:** GraphInsertionAgent  
**Maps to:** [architecture.md](../architecture.md) §3.4, §4 Data model, §5 (Neo4j primary).

## Objective

Implement **GraphInsertionAgent** that maps **DedupReport** + **ExtractionRecord** into **nodes and relationships** with **idempotent upserts** and full **provenance** (`source_run_id`, `snippet_hash`, `extractor_model`, links to artifacts).

This phase builds the **Graph RAG** substrate: Phase 6 retrieves evidence by **graph traversal** (and eventually **Cypher** on Neo4j), not by vector search at query time.

## Prerequisites

- [03_deduplication.md](03_deduplication.md) complete.

## Deliverables (checklist)

> **Status:** baseline implemented for `GRAPH_BACKEND=neo4j` (idempotent node/relationship upserts, constraints, provenance fields, and CLI command).

- [x] Graph backend — **Neo4j** (recommended primary): Python **`neo4j`** driver, constraints, and Cypher upserts when `GRAPH_BACKEND=neo4j`.
- [x] Node labels/properties per architecture §4.1: `Person`, `Organization`, `Location`, `Post`, and provenance-friendly fields.
- [x] Relationships: `CO_APPEARS_WITH`, `TAGGED_IN`, `MENTIONS`, `SOURCED_FROM` (or equivalent naming in code).
- [x] **Idempotency:** stable keys (`canonical_id`, `platform_post_id`, etc.) so reruns update rather than duplicate where enforced.
- [x] **Provenance:** properties on nodes/edges or hashes linking back to run and extraction context.
- [x] **Transaction boundaries:** batch insert with error handling; log offending record.
- [x] Tests: insert same run twice → stable counts where idempotency applies; integrity issues surfaced.

## LangGraph single graph Phase 4

This repo uses **one** LangGraph **`StateGraph`** for the whole **ingest + quality** story ([architecture.md](../architecture.md) §2.4). **Phase 4** implements only the **first** slice (linear path); **Phase 5** extends the **same** graph file/state with `quality` and loop-backs — do **not** start a second LangGraph project for quality.

Once **Phases 1–3** and **GraphInsertionAgent** (above) exist, add LangGraph as the **batch orchestration** layer for the linear path in [architecture.md](../architecture.md) §2.2:

**Flow:** `collect → extract → dedup → graph_insert → END` (no quality node yet; **Phase 5** adds it to this graph).

| # | Deliverable | Notes |
|---|-------------|--------|
| L1 | Dependency | [x] Add `langgraph` (pinned range) to [`pyproject.toml`](../pyproject.toml); document in [`.env.example`](../.env.example) only if new env vars are required. |
| L2 | Module layout | [x] Implement under [`agents/pipeline/`](../src/agents/pipeline/) (`langgraph_runner.py`, `state.py`, `runtime.py`) — **one primary class per file** where applicable ([requirement.md](../requirement.md) §2.1). |
| L3 | `StateGraph` | [x] Typed pipeline state (`PipelineState`: `run_id`, per-stage result dicts, collect inputs). |
| L4 | Nodes | [x] One graph node per stage (`stage_*` names); each calls existing **agent** APIs. |
| L5 | Dev / CI entry | [x] **`python -m cli pipeline`** using **fixtures by default** (`COLLECTION_MODE=fixture`) so CI stays offline. |
| L6 | Tests | [x] [`tests/test_langgraph_pipeline.py`](../tests/test_langgraph_pipeline.py): fixture run completes all four stages; fake graph store asserts non-empty nodes/rels. |

**Out of scope for Phase 4 only:** conditional edges from **Quality** back to **Extract** — add in [05_quality_checking.md](05_quality_checking.md) on the **same** `StateGraph`.

## AuraDB / Neo4j operations

For managed hosting, **Neo4j AuraDB** uses the same Bolt protocol: set `NEO4J_URI`, `NEO4J_USER`, `NEO4J_PASSWORD` in `.env` (never commit values). Prefer **relationship properties** for provenance (for example weights, `snippet_hash`, `extractor_model_id`) and explicit **SOURCED_FROM** / **EXTRACTED_FROM** edges to `Post` or `Artifact` as in [architecture.md](../architecture.md) §3.4.

## Graph-first teaching path

Per [architecture.md](../architecture.md) §5.2 **Path A**, you may define **Cypher constraints** and **seed** a tiny graph **before** the full ingest pipeline is finished, to unblock Phase 6 demos.

## Implementation tasks

1. Define **Cypher** uniqueness constraints for Neo4j (when backend lands); mirror uniqueness in SQLite via primary keys / indexes.
2. Compute **`snippet_hash`** from supporting text for traceability.
3. Map each extracted edge to graph patterns; attach `run_id` to created elements.
4. Optional: wipe dev graph between runs — [`scripts/wipe_neo4j.py`](../scripts/wipe_neo4j.py) or **`python -m cli graph-wipe --yes`** (uses `.env` `NEO4J_*`; constraints stay; data only is cleared).

## Data contracts

**Input:** `DedupReport`, `ExtractionRecord`s, `RawArtifact` refs.  
**Output:** mutation summary (`nodes_created`, `relationships_created`, `transaction_id`).

## Acceptance criteria

- Fixture pipeline through insertion yields a graph queryable for “posts tagged with X” on minimal data (Neo4j).
- Provenance fields retrievable for at least one `Person`–`Post` edge.
- The graph schema is rich enough that Phase 6 can use read-only traversal as the retriever in Graph RAG.
- **LangGraph:** fixture-only run completes the **four-node** linear graph end-to-end (see § LangGraph single graph Phase 4); CI does not require live Instagram.

## Out of scope

- **LangGraph quality loop** (conditional routing); see **Phase 5** and [architecture.md](../architecture.md) §2.3.
- NL query interface (Phase 6).

## Next phase

→ [05_quality_checking.md](05_quality_checking.md)
