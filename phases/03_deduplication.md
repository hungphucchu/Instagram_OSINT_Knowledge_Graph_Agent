# Phase 3 — Deduplication

**Agent:** DedupAgent  
**Maps to:** [architecture.md](../architecture.md) §3.3, §5 (RapidFuzz, embeddings).

## Objective

Implement **DedupAgent** that clusters near-duplicate mentions/entities using **fuzzy string matching** and an **embedding gate**, outputting a **DedupReport** with **`canonical_id`**, merge decisions, scores, **thresholds_used**, and an **immutable audit log**.

## Implementation approach (when you build Phase 3)

Use **RapidFuzz** gating plus an embedding gate: a **deterministic char n-gram** backend keeps CI offline; **sentence-transformers** (for example **`all-MiniLM-L6-v2`**) is a strong optional upgrade. Add dedup thresholds to [`Settings`](../src/config.py) when you extend `config.py`.

## Prerequisites

- [02_extraction.md](02_extraction.md) complete: `ExtractionRecord`s for a `run_id`.

**LangGraph:** `DedupAgent` is invoked from a **LangGraph** node in **Phase 4** ([04_graph_insertion.md](04_graph_insertion.md#langgraph-single-graph-phase-4)).

## Deliverables (checklist)

> **Status:** [`agents/deduplication/`](../src/agents/deduplication/) baseline is implemented (deterministic fuzzy + char n-gram dedup with SQLite report/audit persistence).

- [x] **Fuzzy stage:** RapidFuzz on normalized strings (handles, lowercased names, collapsed whitespace).
- [x] **Embedding gate:** **char n-gram** vectors + cosine similarity; optional **`embedding_backend=off`** for fuzzy-only mode.
- [ ] **Semantic stage (stretch):** `sentence-transformers` (`all-MiniLM-L6-v2` or chosen model) and/or embedding API keyed from `.env`; cosine similarity on shortlisted pairs.
- [x] **Clustering / union-find:** merge only if configured fuzzy + embedding gates pass.
- [x] **`DedupReport`**: clusters, `canonical_id`, aliases, per-pair scores, `thresholds_used`, rationale enum (`fuzzy_only`, `embedding_confirmed`, `human_review` flag).
- [x] **Audit log** append-only: merge decisions with source mention ids.
- [x] Tests: synthetic duplicates merge; distinct names stay split; ambiguous case flagged where applicable.

## Implementation tasks

1. Define **blocking keys** (e.g. first token + length bucket) to scale pairwise comparisons.
2. Optional **embedding cache** per mention id for reuse (architecture §2); can be in-memory for course scope.
3. Conservative defaults: prefer false split over wrong merge; wire flags for QualityAgent.
4. **Stretch:** add `sentence-transformers` backend implementing the same embedding interface as char n-grams.

## Data contracts

**Input:** `ExtractionRecord` batch (+ optional precomputed embeddings).  
**Output:** `DedupReport` + audit log; ready for GraphInsertionAgent.

## Acceptance criteria

- Dedup is deterministic given fixed thresholds and embedding backend version recorded in the report.
- No merge without exceeding configured thresholds; ambiguous cases carry `human_review` or similar.

## Out of scope

- Neo4j schema enforcement (Phase 4); NL queries.

## Next phase

→ [04_graph_insertion.md](04_graph_insertion.md)
