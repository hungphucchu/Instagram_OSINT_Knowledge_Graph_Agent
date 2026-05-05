#!/usr/bin/env python3
"""Convert Locust CSV output into rubric-friendly benchmark artifacts."""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

REPORTS = Path("reports")
STATS_CSV = REPORTS / "loadtest_stats.csv"
FAILURES_CSV = REPORTS / "loadtest_failures.csv"
EXCEPTIONS_CSV = REPORTS / "loadtest_exceptions.csv"
BENCHMARKS_JSON = REPORTS / "benchmarks.json"
STATUS_TXT = REPORTS / "loadtest_status.txt"

HEADLINE_NAME = "POST /api/query"
MIN_RPS = 10.0
MAX_ERROR_RATE = 0.05


def _read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def _to_float(value: str | None) -> float:
    if value is None:
        return 0.0
    value = value.strip()
    if not value:
        return 0.0
    try:
        return float(value)
    except ValueError:
        return 0.0


def _to_int(value: str | None) -> int:
    return int(round(_to_float(value)))


def _pick_headline_row(rows: list[dict[str, str]]) -> dict[str, str]:
    for row in rows:
        if row.get("Name") == HEADLINE_NAME:
            return row
    for row in rows:
        if row.get("Type") == "Aggregated":
            return row
    return {}


def main() -> int:
    stats_rows = _read_csv(STATS_CSV)
    failure_rows = _read_csv(FAILURES_CSV)
    exception_rows = _read_csv(EXCEPTIONS_CSV)

    headline = _pick_headline_row(stats_rows)
    request_count = _to_int(headline.get("Request Count"))
    failure_count = _to_int(headline.get("Failure Count"))
    requests_per_second = _to_float(headline.get("Requests/s"))
    error_rate = (failure_count / request_count) if request_count else 1.0

    status = "ok" if requests_per_second >= MIN_RPS and error_rate < MAX_ERROR_RATE else "failed"
    STATUS_TXT.write_text(status + "\n", encoding="utf-8")

    payload: dict[str, Any] = {
        "headline_endpoint": HEADLINE_NAME,
        "thresholds": {
            "min_requests_per_second": MIN_RPS,
            "max_error_rate": MAX_ERROR_RATE,
        },
        "summary": {
            "request_count": request_count,
            "failure_count": failure_count,
            "requests_per_second": requests_per_second,
            "error_rate": error_rate,
            "status": status,
            "p50_ms": _to_float(headline.get("50%")),
            "p95_ms": _to_float(headline.get("95%")),
            "p99_ms": _to_float(headline.get("99%")),
            "average_response_time_ms": _to_float(headline.get("Average Response Time")),
            "max_response_time_ms": _to_float(headline.get("Max Response Time")),
        },
        "raw": {
            "stats_rows": stats_rows,
            "failure_rows": failure_rows,
            "exception_rows": exception_rows,
        },
    }
    BENCHMARKS_JSON.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(payload["summary"], indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
