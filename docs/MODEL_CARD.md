# Model Card — Instagram OSINT Knowledge Graph Agent

The system uses one or two LLM call sites depending on configuration:

* **Cypher translator** — translates the user's natural-language question into
  a single read-only Cypher query grounded in a live graph schema summary.
* **Answer synthesizer** — produces a short user-friendly answer from the
  rows returned by Cypher. Disabled when `QUERY_LLM_ENABLED=false`; the
  generator then returns a deterministic evidence summary.

Both call sites use the same OpenAI-compatible client. The default deployment
points at the UTSA-hosted Qwen3-8B endpoint (see `grading/manifest.yaml`).

## Intended Use

OSINT analysts and academic researchers exploring **public** Instagram
activity. The intended users are familiar with the difference between
"the graph said X" and "X is true": every answer carries the supporting rows
(`citations`) and the executed Cypher (`cypher`) so the user can verify the
claim themselves.

Typical questions it answers well:

* Co-occurrence patterns ("Who appears together most often?")
* Frequency rollups ("What hashtags appear most with @utsa?")
* Path queries ("How is account A connected to account B?")

## Limitations

* **Knowledge cutoff:** the graph contains only what the ingest pipeline has
  processed. Newly-created posts are not visible until a fresh ingest run
  finishes.
* **Schema-bound:** the Cypher translator only references labels, relationship
  types and properties present in the live schema. Questions that require
  joins across labels we never created return "no evidence" rather than
  inventing data.
* **English-only:** the LLM prompts are tuned for English. Non-English
  questions still parse but quality degrades.
* **Single-hop reasoning:** complex multi-hop reasoning (≥3 hops with
  arithmetic) often produces overly long Cypher that the safety guard
  trims to `LIMIT QUERY_MAX_LIMIT` (default 50).
* **No real-time access:** every answer is grounded in the offline graph; the
  system never calls Instagram while answering a question.
* **No image/video understanding:** captions and structured metadata only.

## Risks

| Risk             | Mitigation                                                                                                                |
| ---------------- | ------------------------------------------------------------------------------------------------------------------------- |
| Hallucination    | Generator is *grounded*: it sees only the rows returned by Cypher; a contradiction guard rejects "no evidence" answers when rows are present. |
| Prompt injection | The user's question is concatenated as a `Question:` field with strict JSON output requirements; we never execute LLM-suggested code. |
| Cypher injection | `agents.query.cypher_guard.verify_read_only_cypher` rejects any clause that mutates state (`CREATE`, `MERGE`, `SET`, `DELETE`, `CALL`, `LOAD CSV`). |
| Bias             | The graph reflects whatever Instagram's public discovery shows. Underrepresented communities will be underrepresented in answers. |
| Privacy          | Only public posts are ingested. Request bodies are logged at INFO level with a `text_length` field but **not** the question text itself. |
| Cost             | All LLM calls cap `max_tokens` (220 for Cypher translation, 256 for answer synthesis), `temperature=0`, and Cypher results are capped to `QUERY_MAX_LIMIT` rows. |

## Out of Scope

* Medical, legal, or financial advice.
* Identifying or tracking individuals beyond what their public Instagram
  profile already reveals.
* Real-time conversation, voice or multimedia.
* File uploads or arbitrary code execution by the model.
* Mutating the graph from the query API. The query path is strictly read-only;
  ingest is a separate, explicit, operator-driven flow.
