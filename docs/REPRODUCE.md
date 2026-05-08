# Reproducibility Procedure

## Procedure

```bash
# From a fresh clone with .env populated
make reproduce
```

`make reproduce` performs these steps in order:

1. `docker compose down -v --remove-orphans` to clear the prior graph/runtime.
2. `docker compose up --build -d` with `QUERY_LLM_ENABLED=false` so the live
   stack can answer the headline query deterministically without paid inference.
3. Waits for `GET /health` on `http://localhost:8080/health`.
4. Stages `fixtures/raw_artifacts.json` into `data/` and writes
   `reports/download_models.txt` documenting model provenance.
5. Runs the sample ingest in the app container:
   `PYTHONPATH=src python -m myproject.pipeline --sample`
6. Runs the full pytest suite in the app container, writing:
   `reports/unit.xml`, `integration.xml`, `user_stories.xml`, `edge.xml`,
   and `coverage.xml`.
7. Runs the 60-second Locust load test against `POST /api/query` and writes
   `reports/benchmarks.json`.
8. Leaves the compose stack up for manual inspection; the reviewer may later run
   `docker compose down`.

## Hardware Profile

Headline numbers were measured on:

- CPU: Apple Silicon M2 / Intel x86_64 (8 cores)
- Memory: 16 GB
- Disk: 50 GB free
- Network: not required for the default replay path beyond Docker image pulls
- GPU: not required

## Expected Wall Clock

| Stage                                | Budget        |
| ------------------------------------ | ------------- |
| Docker build + compose health        | < 10 minutes  |
| Fixture staging + model provenance   | < 5 seconds   |
| Sample pipeline (`--sample`)         | < 30 seconds  |
| Test suite (`pytest`)                | < 5 minutes   |
| Load test + benchmark summarisation  | < 2 minutes   |
| **Total `make reproduce`**           | **< 30 min**  |

## Expected Outputs

After `make reproduce` completes, the following files exist:

- `reports/unit.xml`
- `reports/integration.xml`
- `reports/user_stories.xml`
- `reports/edge.xml`
- `reports/coverage.xml`
- `reports/coverage_html/index.html`
- `reports/reproduce_pipeline.json`
- `reports/benchmarks.json`
- `reports/download_models.txt`

## Expected Metric Values

| Metric                                       | Expected | Tolerance | Where measured                              |
| -------------------------------------------- | -------- | --------- | ------------------------------------------- |
| Sample pipeline raw artifacts ingested       | 2        | exact     | stdout of `python -m myproject.pipeline`    |
| Sample pipeline extraction records written   | 2        | exact     | same                                        |
| Sample pipeline dedup clusters               | 10       | exact     | same                                        |
| Test coverage on `src/myproject/`            | 0.86     | ± 0.05    | `reports/coverage.xml` (`line-rate` attr)   |
| User-story test pass rate                    | 1.00     | ≥ 0.90    | `reports/user_stories.xml`                  |
| `POST /api/query` p95 latency (LLM disabled) | 21 ms    | ± 100 ms  | `reports/benchmarks.json`                   |
| Sustained load throughput                    | ≥ 10 rps | exact     | `reports/benchmarks.json`                   |
| Load-test error rate (60 s window)           | < 5 %    | exact     | `reports/benchmarks.json`                   |

## Outside Tolerance?

If a metric drifts outside the documented tolerance:

- The Reproducibility test row scores 5/10 instead of 10/10.
- The team is expected to investigate and document the cause in
  `reports/known_issues.md` if the deadline has not passed.
