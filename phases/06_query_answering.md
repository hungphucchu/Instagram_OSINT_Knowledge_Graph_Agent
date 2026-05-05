# Phase 6 — Query answering

**Agent:** QueryAgent  
**Maps to:** [architecture.md](../architecture.md) §3.6, §5 (NL → Cypher + verifier using LangChain/LlamaIndex/custom agent patterns).

## Objective

Implement **QueryAgent** that uses **Graph RAG** over the knowledge graph: accept **natural language** questions, produce a **read-only bounded** graph query (e.g. **Cypher** on Neo4j, or equivalent traversal on SQLite lite), execute it, and return a natural language answer **grounded** in result rows with **evidence** (node ids, edge ids, query text, provenance pointers).

**Reference integration:** use **LangChain** or **LlamaIndex** text-to-Cypher chains, or a custom **Claude/GPT** agent with graph-retrieval tools, for **NL → Cypher → execute → answer**. Keep this project’s **read-only verifier** and optional **`CollaborativeLLMPair.generate_and_verify_cypher`** so one model drafts and another verifies safety and question fit.

Graph RAG here means the **graph is the retriever**; **no query-time embeddings** — embeddings remain in Phase 3 for deduplication only.

### LangGraph (default: do not use a second graph)

Per [architecture.md](../architecture.md) §2.4, **QueryAgent** is **not** a node on the **single** ingest/quality LangGraph. Implement Q&A as **API handlers** that call **QueryAgent** services (NL → verify → Cypher → execute → answer). An optional **tiny** internal helper chain is fine; a **second full LangGraph** for “only Phase 6” is **out of default scope** unless you document a deliberate exception.

## Prerequisites

- [04_graph_insertion.md](04_graph_insertion.md) complete; [05_quality_checking.md](05_quality_checking.md) recommended so bad data can be flagged before demos.

## Graph-first path

Per [architecture.md](../architecture.md) §5.2 **Path A**, Phase 6 can begin with **manually seeded Neo4j** (or a tiny SQLite graph) so students prove **Cypher + evidence** before the full LangGraph ingest loop is finished.

## Deliverables (checklist)

- [ ] **Schema summary** builder: node labels, relationship types, sample properties (injected into prompt or template).
- [ ] **Query generation:** LLM or template+LLM hybrid → candidate Cypher (or SQL/traversal plan in lite mode) that retrieves a subgraph.
- [ ] **Dual-model Cypher path (optional):** `CollaborativeLLMPair.generate_and_verify_cypher` — one model drafts Cypher with a hard `LIMIT`, the other verifies read-only + fit; log `draft_query` vs final `query` when they differ.
- [ ] **Verifier:** reject non-readonly queries (block `CREATE`, `DELETE`, `MERGE`, `SET`, `REMOVE`, `DROP`, etc.); enforce **`LIMIT`** and **timeouts**; optional allowlist of clause patterns.
- [ ] **Executor:** run against Neo4j or SQLite graph store; capture tabular results.
- [ ] **Answer synthesizer:** NL answer **only** from result JSON; include **evidence** section listing ids and key properties.
- [ ] **Logging:** `query_id`, generated query, result row count, checksum.
- [ ] **Framework/agent front-end (optional stretch):** wire **LangChain** (`GraphCypherQAChain` or successor), **LlamaIndex** text-to-Cypher, or a custom **Claude/GPT** graph-tools agent as the NL→Cypher→answer front-end, still passing generated Cypher through the verifier before execution.
- [ ] **Demo questions:** e.g. “Which pair of people co-appeared most often?” backed by `CO_APPEARS_WITH` counts from the graph.
- [ ] **No query-time embeddings:** document explicitly in API docs and README.
- [ ] Tests: verifier blocks mutation; empty graph returns explicit “no evidence”; golden questions on fixture graph.

### Status update (baseline implementation)

- [x] **Schema summary** builder implemented in `QueryAgent` via graph introspection (`DISTINCT labels`, `DISTINCT type(r)`).
- [x] **Query generation** implemented with deterministic templates first (e.g. co-appear / mentions), optional LLM fallback.
- [x] **Verifier** implemented (`agents/query/cypher_guard.py`): blocks mutating clauses and enforces `LIMIT`.
- [x] **Executor** implemented via Neo4j `run_read(...)` in graph store.
- [x] **Answer envelope** implemented: `{answer, evidence, cypher, query_id, warnings}`.
- [x] **CLI command** implemented: `python -m cli query --question "..."`
- [x] **Tests** added for mutation blocking, LIMIT enforcement, empty evidence behavior.

## Implementation tasks

1. Define response envelope: `{ answer, evidence: [...], cypher, query_id, warnings }`.
2. Handle **empty results** without inventing entities (architecture §8).
3. Optional: graph-neighborhood expansion (k-hop paths, relationship filters, schema-guided traversal) before Cypher generation for large graphs.
4. Document required env vars for LLM provider in `.env.example`.

## Data contracts

**Input:** natural language `question`, session id optional.  
**Output:** grounded answer + evidence + optional `cypher` field for audit.

## Acceptance criteria

- Demo NL questions run against fixture-derived graph and return cited evidence.
- Mutating generated queries are rejected 100% in test suite.
- End-to-end story: Phase 0–6 runnable on fixtures without Instagram (Path B), or Path A with seeded Neo4j.

## Out of scope

- Production auth for multi-user API (optional stretch).

## Pipeline complete

All six agents operational; see [architecture.md](../architecture.md) for risks and cross-cutting concerns.
