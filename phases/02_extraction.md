# Phase 2 — Extraction

**Agent:** ExtractionAgent  
**Maps to:** [architecture.md](../architecture.md) §3.2, §5 (NLP, LLM, Graph RAG context).

## Objective

Implement **ExtractionAgent** that reads **RawArtifactStore** by **`run_id`**, emits **ExtractionRecord**s (entities + relations + confidence), linked to **`artifact_id`** and **`extractor_model_id`**, with basic evaluation on fixtures.

**Recommended stack (architecture):** **Instructor** + hosted LLM (**Claude/GPT**) is the default for caption relationship extraction with strict JSON; keep this repo’s **heuristic** path for CI/offline; optionally merge **GLiNER** local spans for better recall.

## Prerequisites

- [01_collection.md](01_collection.md) complete: artifacts in store.

**LangGraph:** `ExtractionAgent` is invoked from a **LangGraph** node in **Phase 4** ([04_graph_insertion.md](04_graph_insertion.md#langgraph-single-graph-phase-4)); keep orchestration out of the agent module.

## Deliverables (checklist)

> **Status:** baseline implementation now exists in [`agents/extraction/`](../src/agents/extraction/) with heuristic extraction, LLM-ready interface, SQLite `ExtractionStore`, and CLI `extract` command.

- [ ] **`ExtractionRecord`** schema: entities (type, surface form, optional offsets/snippet), relations (subject, predicate, object, confidence), `artifact_id`, `run_id`, `extractor_model_id`.
- [ ] **`ExtractionAgent`**: batch artifacts; **LLM extraction default** for relations from captions (subject, predicate, object, confidence, evidence span), with schema-validated JSON.
- [ ] **Fallback path:** **heuristic** extraction (hashtags, @mentions, co-occurrence) available offline/CI; record which mode produced each row.
- [ ] Persistence of extraction rows per `run_id` (SQLite store) for downstream Dedup.
- [ ] **Evaluation:** on fixture set, precision/recall or slot-filling vs optional hand-labeled gold (recommended stretch).
- [ ] Tests: known caption produces expected entity types; malformed input skipped with logged reason.
- [ ] **Instructor (default path):** Pydantic-validated `ExtractionRecord`-shaped JSON in one call.
- [ ] **GLiNER (optional stretch):** local NER pass merged with heuristics/LLM for cost-sensitive runs.

**Target layout:** one primary class per file under `agents/extraction/`. Prefer **API** endpoints (or async jobs) for extraction runs; any **`extract` dev CLI** should delegate to the same application code the API uses.

## Configuration (.env)

Reintroduce when implementing Phase 2 (see [architecture.md](../architecture.md) §5.3): `EXTRACT_MODE`, `EXTRACT_LLM_PROVIDER`, `EXTRACT_LLM_MODEL`, `UTSA_*`, `LLM_COLLAB_MODE`, `LLM_EXTRACT_LEADER`.

## Implementation tasks

1. Normalize text from caption/bio fields; define max length and encoding.
2. Map labels to architecture entity kinds where possible (`Person`, `Organization`, `Location`).
3. Run LLM-first relation extraction for caption text, then optionally add heuristic **CO_APPEARS_WITH** / **TAGGED_IN** / **MENTIONS** candidates from hashtags, @mentions, and co-occurrence as fallback/recall boosts.
4. Flag low-confidence extractions for later QualityAgent.

## Data contracts

**Input:** `run_id` (+ optional artifact ids).  
**Output:** `ExtractionRecord` list with provenance to artifact and model version.

## Acceptance criteria

- End-to-end: fixture run → collection → extraction produces non-empty records for at least one fixture.
- Parser errors do not crash the run; failures recorded per §3.2.

## Out of scope

- Canonical entity resolution (Phase 3); graph writes (Phase 4).

## Next phase

→ [03_deduplication.md](03_deduplication.md)
