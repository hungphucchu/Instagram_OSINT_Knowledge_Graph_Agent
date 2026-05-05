# Phase 5 — Quality checking

**Agent:** QualityAgent  
**Maps to:** [architecture.md](../architecture.md) §3.5, §7 Cross-cutting, §2.3 (quality loop on the ingest graph).

## Objective

Implement **QualityAgent** that reads the **knowledge graph** (read-only), runs **validation rules**, and emits a **QualityReport** with metrics and suggested fixes — **no silent delete** without explicit policy.

**LangGraph:** extend the **same single `StateGraph`** built in [Phase 4](04_graph_insertion.md#langgraph-single-graph-phase-4) ([architecture.md](../architecture.md) §2.4). Add the **`quality`** node and conditional routing there; do **not** introduce a second LangGraph application for batch work.

**Recommended stack:** deterministic **rule packs** first; add an **LLM judge agent** that samples graph nodes/edges (plus source text and extraction JSON) and flags anomalies with structured reasons; **Guardrails AI** (or similar) to enforce **schema** and **source URL / artifact presence** before trusting inserts. When orchestration grows, **LangGraph** should add a conditional edge from **QualityJudge** back to **Extraction** (or **Dedup**) on failure — see [architecture.md](../architecture.md) §2.3.

## Prerequisites

- [04_graph_insertion.md](04_graph_insertion.md) complete: populated graph.

## Deliverables (checklist)

- [x] **LLM-only quality mode:** deterministic graph rule pack removed; quality checks are now driven by LLM judge findings from extraction-vs-source samples.
- [ ] **Dedup-related checks:** not implemented in LLM-only mode (was formerly deterministic graph rules).
- [x] **Extraction checks (LLM judge):** sampled `raw_artifacts` + `extraction_records` are judged for semantic consistency and returned as `llm_judge_extraction_mismatch` findings.
- [x] **`QualityReport`**: JSON on disk under `QUALITY_REPORT_DIR` (`reports/` default), Pydantic model in [`schemas/quality_report.py`](../src/schemas/quality_report.py) (`suggested_fixes` field reserved for future hints).
- [x] **Quarantine workflow (baseline):** `reports/quarantine_{run_id}.json` written when **critical** violations exist (for future QueryAgent `include_quarantined` — not wired until Phase 6).
- [x] **LLM judge sampling pass (configurable):** optional extraction-vs-source sampling with env-config (`QUALITY_LLM_ENABLED`, `QUALITY_LLM_PROVIDER`, `QUALITY_LLM_MODEL`, `QUALITY_LLM_BASE_URL`, `QUALITY_LLM_API_KEY`, `QUALITY_LLM_TIMEOUT_SECONDS`, `QUALITY_LLM_SAMPLE_SIZE`, `QUALITY_LLM_MAX_CONCURRENCY`, `QUALITY_LLM_MIN_SCORE_THRESHOLD`). Produces warning violations (`llm_judge_extraction_mismatch`) in `QualityReport`; disabled by default.
- [ ] **Guardrails-style validation (optional stretch):** not implemented.
- [x] Tests: [`tests/test_quality_rules.py`](../tests/test_quality_rules.py) + LangGraph fixture pipeline exercises quality after graph insert; quality node wraps errors as `quality.status=error` (router ends without claiming pass).
- [x] **LangGraph:** same `StateGraph` as Phase 4 — `stage_quality` after `graph_insert`; on fail, retry to **`QUALITY_RETRY_TARGET`** (`extract` | `dedup`) until `QUALITY_MAX_ATTEMPTS`; on pass or exhaustion, `END`. CLI: `python -m cli quality --run-id …`, `python -m cli pipeline …`.

## Implementation tasks

1. **Implemented:** LLM judge samples extraction outputs with configurable endpoint/model/timeouts.
2. **Implemented:** `reports/quality_{run_id}_{timestamp}.json` (override with `QUALITY_REPORT_DIR`).
3. Document escalation: instructor review for `human_review` items from Phase 3.

## Data contracts

**Input:** graph connection + optional `run_id` filter; `rule_pack_version`.  
**Output:** `QualityReport` artifact on disk or object store.

## Acceptance criteria

- Running QualityAgent after a good fixture run produces zero critical violations (baseline).
- Injected orphan edge triggers violation with id and rule name.
- Aligns with §3.5: no automatic destructive fixes unless config explicitly enables a named policy.

## Out of scope

- Natural-language answers (Phase 6).

## Next phase

→ [06_query_answering.md](06_query_answering.md)
