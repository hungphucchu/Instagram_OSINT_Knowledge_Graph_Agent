# Models

## Model 1: Qwen3-8B (default Cypher translator + answer synthesizer)

- **Source:** UTSA-hosted OpenAI-compatible inference endpoint
- **Identifier:** `Qwen/Qwen3-8B`
- **Revision/version:** as deployed on `http://149.165.171.140:8888/v1`
  (see `QUERY_LLM_BASE_URL` in `.env`)
- **License:** Apache 2.0 (Qwen3 weights), with the hosted endpoint covered
  by UTSA's class-issued credentials.
- **Size:** API only — no local weights.
- **Used for:** NL → Cypher translation and grounded answer synthesis in
  `agents.query.QueryAgent`. Optionally used by the LLM-as-judge pass in
  `agents.quality.QualityAgent`.

### Access

API-based; only needs credentials in `.env`:

```ini
QUERY_LLM_ENABLED=true
QUERY_LLM_PROVIDER=openai
QUERY_LLM_MODEL=Qwen/Qwen3-8B
QUERY_LLM_BASE_URL=http://149.165.171.140:8888/v1
QUERY_LLM_API_KEY=<your utsa-issued bearer token>
```

The `make download-models` target prints the access requirements; nothing
needs to be fetched locally.

## Model 2: Llama-3.1-8B-Instruct (extraction + quality fallback)

- **Source:** UTSA-hosted OpenAI-compatible inference endpoint
- **Identifier:** `meta-llama/Llama-3.1-8B-Instruct`
- **Revision/version:** deployed on `http://149.165.173.247:8888/v1`
- **License:** Meta Llama 3 Community License.
- **Used for:** entity / relation extraction
  (`agents.extraction.LLMExtractor`) and the LLM-as-judge quality pass
  (`agents.quality.LLMJudge`).

### Access

```ini
EXTRACT_MODE=llm
EXTRACT_LLM_PROVIDER=openai
EXTRACT_LLM_MODEL=meta-llama/Llama-3.1-8B-Instruct
EXTRACT_LLM_BASE_URL=http://149.165.173.247:8888/v1
EXTRACT_LLM_API_KEY=<your utsa-issued bearer token>
```

## Model 3: Anthropic Claude (regeneration test only)

- **Identifier:** `claude-opus-4-5-20251101` (course-pinned in
  `scripts/regenerate.sh`)
- **Used for:** the rubric's spec-regeneration test only. The application
  itself does not call Claude.
- **Access:** `ANTHROPIC_API_KEY` in `.env`. Only needed when running
  `scripts/regenerate.sh` or `bash scripts/preflight.sh`.
