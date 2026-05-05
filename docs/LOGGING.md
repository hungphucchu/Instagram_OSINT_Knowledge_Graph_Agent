# Logging

> The Logging category test (5 pts) is graded by the TA tracing one request
> end-to-end through `docker compose logs -f app` using its request id.

## Format

All log entries are JSON, one entry per line, written to stdout. Format:

```json
{
  "timestamp": "2026-04-28T14:32:01.234567+00:00",
  "level":     "INFO",
  "module":    "myproject.api",
  "request_id":"req_a1b2c3d4",
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

`POST /api/query` with `{"text": "Who appeared together most often?"}`. The
captured request id is `req_a1b2c3d4`. Below are the log lines produced
end-to-end (filter with `docker compose logs -f app | grep req_a1b2c3d4`):

```json
{"timestamp":"2026-04-28T14:32:01.001+00:00","level":"INFO","module":"myproject.api","request_id":"req_a1b2c3d4","message":"request_started","extra":{"method":"POST","path":"/api/query"}}
{"timestamp":"2026-04-28T14:32:01.005+00:00","level":"INFO","module":"myproject.router","request_id":"req_a1b2c3d4","message":"received_query","extra":{"text_length":36,"max_results":5}}
{"timestamp":"2026-04-28T14:32:01.452+00:00","level":"INFO","module":"query.agent","request_id":"req_a1b2c3d4","message":"query_llm_raw_cypher_response={...}"}
{"timestamp":"2026-04-28T14:32:01.612+00:00","level":"INFO","module":"myproject.retriever","request_id":"req_a1b2c3d4","message":"retriever_search_complete","extra":{"k":50,"hits":12}}
{"timestamp":"2026-04-28T14:32:02.244+00:00","level":"INFO","module":"myproject.generator","request_id":"req_a1b2c3d4","message":"generator_llm_complete","extra":{"latency_ms":631,"characters":182}}
{"timestamp":"2026-04-28T14:32:02.260+00:00","level":"INFO","module":"myproject.router","request_id":"req_a1b2c3d4","message":"response_ready","extra":{"latency_ms":1259,"citations":5,"warnings":0,"request_id":"req_a1b2c3d4"}}
{"timestamp":"2026-04-28T14:32:02.265+00:00","level":"INFO","module":"myproject.api","request_id":"req_a1b2c3d4","message":"request_finished","extra":{"status":200}}
```

The TA can read this trace top-to-bottom to confirm:

1. Request arrival (`request_started`)
2. Routing (`received_query`)
3. LLM call (`query_llm_raw_cypher_response`)
4. Retrieval (`retriever_search_complete`)
5. Answer synthesis (`generator_llm_complete`)
6. Response sent (`response_ready`, `request_finished`)

If the TA can do this for any request without reading source code, the
Logging category scores full credit.
