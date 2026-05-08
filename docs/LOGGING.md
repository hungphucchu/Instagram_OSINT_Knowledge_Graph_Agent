# Logging

> This document shows how to trace one request end-to-end through
> `docker compose logs -f app` using its request id.

## Format

All log entries are JSON, one entry per line, written to stdout. Format:

```json
{
  "timestamp": "2026-04-28T14:32:01.234567+00:00",
  "level":     "INFO",
  "module":    "myproject.api",
  "request_id":"req_bf6d39d6",
  "message":   "request_started",
  "extra":     {"method": "POST", "path": "/api/query"}
}
```

Required fields: `timestamp`, `level`, `module`, `request_id`, `message`.
Optional: `extra` (an object with arbitrary key/value pairs) and `exc_info`.

The formatter lives in `src/myproject/logging_setup.py`.

## Levels

- `DEBUG` — internal trace, off by default.
- `INFO` — normal events (request received, response sent, ingest progress).
- `WARNING` — recoverable issues (LLM truncation, slow upstream, rejected
  Cypher).
- `ERROR` — request failed despite retries.

The application sets level via `LOG_LEVEL` in `.env`; default is `INFO`.

## Request ID Propagation

`api._request_id_middleware` allocates a new `request_id` on every incoming
request (or honours one supplied via the `X-Request-ID` header) and binds it
to a `contextvars.ContextVar`. Any logger that goes through the standard
`logging` module picks the id up via `_RequestIdFilter` and emits it on
every record, so every component touched by the request prints a log line
tagged with the same id. The same id is echoed back to the client via the
`X-Request-ID` response header.

## Worked Example

`POST /api/query` with a natural-language question. The captured request id is
`req_bf6d39d6`. Below are real log lines from a live run (filter with
`docker compose logs -f app | grep req_bf6d39d6`):

```json
instagram_osint_kg_backend | {"timestamp": "2026-05-07T06:33:50.202976+00:00", "level": "INFO", "module": "myproject.api", "request_id": "req_bf6d39d6", "message": "request_started", "extra": {"method": "POST", "path": "/api/query"}}

instagram_osint_kg_backend | {"timestamp": "2026-05-07T06:33:50.203998+00:00", "level": "INFO", "module": "myproject.router", "request_id": "req_bf6d39d6", "message": "received_query", "extra": {"text_length": 33, "max_results": 5}}

instagram_osint_kg_backend | {"timestamp": "2026-05-07T06:33:50.247907+00:00", "level": "INFO", "module": "extraction.llm_client", "request_id": "req_bf6d39d6", "message": "llm_request_start model=Qwen/Qwen3-8B timeout_seconds=60 messages=2 max_tokens=220 max_retries=0"}

instagram_osint_kg_backend | {"timestamp": "2026-05-07T06:33:51.278733+00:00", "level": "INFO", "module": "extraction.llm_client", "request_id": "req_bf6d39d6", "message": "llm_request_done model=Qwen/Qwen3-8B elapsed_ms=1030"}

instagram_osint_kg_backend | {"timestamp": "2026-05-07T06:33:51.278906+00:00", "level": "INFO", "module": "query.agent", "request_id": "req_bf6d39d6", "message": "query_llm_raw_cypher_response={\"id\": \"chatcmpl-91146fda959a379b\", \"choices\": [{\"finish_reason\": \"stop\", \"index\": 0, \"logprobs\": null, \"message\": {\"content\": \"<think>\\n\\n</think>\\n\\n{\\\"cypher\\\":\\\"MATCH (c1:CanonicalEntity)-[:COLLABORATES_WITH]->(c2:CanonicalEntity) RETURN c1, c2, COUNT((c1)-[:COLLABORATES_WITH]->(c2)) AS collaborationCount ORDER BY collaborationCount DESC LIMIT 50\\\"}\", \"refusal\": null, \"role\": \"assistant\", \"function_call\": null, \"tool_calls\": [], \"annotations\": null, \"audio\": null, \"reasoning\": null, \"reasoning_content\": null}, \"stop_reason\": null, \"token_ids\": null}], \"created\": 1778135630, \"model\": \"Qwen/Qwen3-8B\", \"object\": \"chat.completion\", \"service_tier\": null, \"system_fingerprint\": null, \"usage\": {\"completion_tokens\": 67, \"prompt_tokens\": 932, \"total_tokens\": 999, \"prompt_tokens_details\": null}, \"prompt_logprobs\": null, \"prompt_token_ids\": null, \"kv_transfer_params\": null}"}

instagram_osint_kg_backend | {"timestamp": "2026-05-07T06:33:51.284878+00:00", "level": "INFO", "module": "extraction.llm_client", "request_id": "req_bf6d39d6", "message": "llm_request_start model=Qwen/Qwen3-8B timeout_seconds=60 messages=2 max_tokens=220 max_retries=0"}

instagram_osint_kg_backend | {"timestamp": "2026-05-07T06:33:51.793773+00:00", "level": "INFO", "module": "extraction.llm_client", "request_id": "req_bf6d39d6", "message": "llm_request_done model=Qwen/Qwen3-8B elapsed_ms=508"}

instagram_osint_kg_backend | {"timestamp": "2026-05-07T06:33:51.794122+00:00", "level": "INFO", "module": "query.agent", "request_id": "req_bf6d39d6", "message": "query_llm_raw_answer_response={\"id\": \"chatcmpl-9146427374d9d0e8\", \"choices\": [{\"finish_reason\": \"stop\", \"index\": 0, \"logprobs\": null, \"message\": {\"content\": \"<think>\\n\\n</think>\\n\\n{\\\"answer\\\":\\\"Dear New York and Humans of New York appeared together most often with a collaboration count of 2.\\\"}\", \"refusal\": null, \"role\": \"assistant\", \"function_call\": null, \"tool_calls\": [], \"annotations\": null, \"audio\": null, \"reasoning\": null, \"reasoning_content\": null}, \"stop_reason\": null, \"token_ids\": null}], \"created\": 1778135631, \"model\": \"Qwen/Qwen3-8B\", \"object\": \"chat.completion\", \"service_tier\": null, \"system_fingerprint\": null, \"usage\": {\"completion_tokens\": 29, \"prompt_tokens\": 7991, \"total_tokens\": 8020, \"prompt_tokens_details\": null}, \"prompt_logprobs\": null, \"prompt_token_ids\": null, \"kv_transfer_params\": null}"}

instagram_osint_kg_backend | {"timestamp": "2026-05-07T06:33:51.794578+00:00", "level": "INFO", "module": "myproject.router", "request_id": "req_bf6d39d6", "message": "response_ready", "extra": {"latency_ms": 1590, "citations": 5, "warnings": 0, "request_id": "req_bf6d39d6"}}

instagram_osint_kg_backend | {"timestamp": "2026-05-07T06:33:51.795873+00:00", "level": "INFO", "module": "myproject.api", "request_id": "req_bf6d39d6", "message": "request_finished", "extra": {"status": 200}}
```

This trace can be read top-to-bottom to confirm:

1. Request arrival (`request_started`)
2. Routing (`received_query`)
3. Model call start / finish (`llm_request_start`, `llm_request_done`)
4. Cypher generation (`query_llm_raw_cypher_response`)
5. Answer synthesis (`query_llm_raw_answer_response`)
6. Response sent (`response_ready`, `request_finished`)

This gives a complete end-to-end example of how one request moves through the
system using a single captured `request_id`.
