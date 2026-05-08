#!/usr/bin/env bash

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

APP_PORT="${APP_PORT:-8080}"
APP_URL="${APP_URL:-http://localhost:${APP_PORT}}"

mkdir -p reports data apify_data

if ! command -v docker >/dev/null 2>&1; then
  echo "ERROR: docker is not installed or not on PATH." >&2
  echo "Install Docker Desktop (or Docker Engine + Compose), then rerun: make reproduce" >&2
  exit 1
fi

if ! docker compose version >/dev/null 2>&1; then
  echo "ERROR: docker compose is unavailable." >&2
  echo "Install a Docker distribution that includes Compose, then rerun: make reproduce" >&2
  exit 1
fi

if ! docker info >/dev/null 2>&1; then
  echo "ERROR: Docker is installed, but the Docker daemon is not reachable." >&2
  echo "Start Docker Desktop (or the Docker daemon/service) and wait until it is healthy." >&2
  echo "Then rerun: make reproduce" >&2
  exit 1
fi

echo "[reproduce] refreshing grading/manifest.yaml commit_sha if HEAD exists"
python3 - <<'PY'
from pathlib import Path
import subprocess

manifest = Path("grading/manifest.yaml")
text = manifest.read_text()
try:
    sha = subprocess.check_output(
        ["git", "rev-parse", "HEAD"],
        stderr=subprocess.DEVNULL,
        text=True,
    ).strip()
except Exception:
    sha = "NO_GIT_HEAD_AVAILABLE"

lines = []
for line in text.splitlines():
    if line.startswith("commit_sha:"):
        lines.append(f'commit_sha: "{sha}"')
    else:
        lines.append(line)
manifest.write_text("\n".join(lines) + "\n")
print(f"[reproduce] manifest commit_sha={sha}")
PY

echo "[reproduce] tearing down any existing compose stack"
docker compose down -v --remove-orphans || true

echo "[reproduce] building and starting Docker environment"
QUERY_LLM_ENABLED=false docker compose up --build -d

echo "[reproduce] waiting for app health at ${APP_URL}/health"
for _ in $(seq 1 120); do
  if curl -fsS "${APP_URL}/health" >/dev/null 2>&1; then
    echo "[reproduce] app is healthy"
    break
  fi
  sleep 5
done

if ! curl -fsS "${APP_URL}/health" >/dev/null 2>&1; then
  echo "ERROR: app did not become healthy within 10 minutes." >&2
  docker compose ps
  exit 1
fi

echo "[reproduce] running named artifact staging targets"
make download-data
make download-models

echo "[reproduce] running sample pipeline in the app container"
docker compose exec -T app sh -lc \
  'mkdir -p reports data && PYTHONPATH=src python -m myproject.pipeline --sample' \
  > reports/reproduce_pipeline.log

python3 - <<'PY'
from pathlib import Path
import json

log_path = Path("reports/reproduce_pipeline.log")
out_path = Path("reports/reproduce_pipeline.json")
text = log_path.read_text()

start = text.rfind("{")
if start == -1:
    raise SystemExit("ERROR: sample pipeline output did not contain a JSON summary")

summary = text[start:].strip()
out_path.write_text(summary + "\n")
print(f"[reproduce] wrote clean JSON summary to {out_path}")
data = json.loads(summary)
print(
    "[reproduce] sample pipeline summary:",
    f"run_id={data['run_id']}",
    f"raw_artifacts={data['raw_artifacts']}",
    f"extraction_records={data['extraction_records']}",
    f"dedup_clusters={data['dedup_clusters']}",
)
PY

echo "[reproduce] running full test suite in the app container"
docker compose exec -T app sh -lc \
  'mkdir -p reports && \
   PYTHONPATH=src pytest -q tests/unit --junitxml=reports/unit.xml \
     > reports/unit.log 2>&1 || { cat reports/unit.log; exit 1; } && \
   PYTHONPATH=src pytest -q tests/integration --junitxml=reports/integration.xml \
     > reports/integration.log 2>&1 || { cat reports/integration.log; exit 1; } && \
   PYTHONPATH=src pytest -q tests/user_stories --junitxml=reports/user_stories.xml \
     > reports/user_stories.log 2>&1 || { cat reports/user_stories.log; exit 1; } && \
   PYTHONPATH=src pytest -q tests/edge --junitxml=reports/edge.xml \
     > reports/edge.log 2>&1 || { cat reports/edge.log; exit 1; } && \
   PYTHONPATH=src pytest -q --cov=myproject \
      --cov-report=xml:reports/coverage.xml \
      --cov-report=html:reports/coverage_html \
      --cov-fail-under=70 \
      tests/unit tests/integration tests/user_stories \
      > reports/coverage_test.log 2>&1 || { cat reports/coverage_test.log; exit 1; }'

python3 - <<'PY'
import xml.etree.ElementTree as ET
from pathlib import Path

def suite_counts(path: str) -> tuple[int, int, int, int]:
    root = ET.parse(path).getroot()
    suites = root.findall("testsuite") if root.tag == "testsuites" else [root]
    total = sum(int(s.get("tests", 0)) for s in suites)
    failed = sum(int(s.get("failures", 0)) + int(s.get("errors", 0)) for s in suites)
    skipped = sum(int(s.get("skipped", 0)) for s in suites)
    passed = total - failed - skipped
    return total, passed, failed, skipped

for name in ["unit", "integration", "user_stories", "edge"]:
    total, passed, failed, skipped = suite_counts(f"reports/{name}.xml")
    print(f"[reproduce] {name}: passed={passed}/{total} failed={failed} skipped={skipped}")

coverage = ET.parse("reports/coverage.xml").getroot()
line_rate = float(coverage.get("line-rate", "0"))
print(f"[reproduce] coverage: line_rate={line_rate:.2%}")
PY

echo "[reproduce] running load test to regenerate README headline numbers"
run_loadtest_once() {
  rm -f reports/loadtest.log
  docker compose exec -T app sh -lc \
    'mkdir -p reports && \
     locust -f tests/load/locustfile.py \
       --headless --only-summary -u 20 -r 5 -t 60s \
       --host=http://localhost:8080 \
       --csv=reports/loadtest && \
     PYTHONPATH=src python scripts/summarize_loadtest.py --quiet' \
    > reports/loadtest.log 2>&1 &
  loadtest_pid=$!
  trap 'kill $loadtest_pid 2>/dev/null || true' INT TERM
  echo "[reproduce] load test started (expected duration: about 60 seconds)"
  elapsed=0
  while kill -0 "$loadtest_pid" 2>/dev/null; do
    echo "[reproduce] load test still running... ${elapsed}s elapsed"
    sleep 5
    elapsed=$((elapsed + 5))
  done
  if ! wait "$loadtest_pid"; then
    return 1
  fi
  return 0
}

if ! run_loadtest_once; then
  echo "[reproduce] load test attempt 1 failed; retrying once after 5 seconds..."
  cat reports/loadtest.log || true
  sleep 5
  if ! run_loadtest_once; then
    echo "[reproduce] load test attempt 2 failed."
    cat reports/loadtest.log || true
    echo "[reproduce] docker compose ps snapshot:"
    docker compose ps || true
    echo "[reproduce] recent backend logs:"
    docker compose logs --tail=120 app || true
    exit 1
  fi
fi

python3 - <<'PY'
import json
from pathlib import Path

bench = json.loads(Path("reports/benchmarks.json").read_text())
summary = bench["summary"]
print(
    "[reproduce] loadtest summary:",
    f"rps={summary['requests_per_second']:.2f}",
    f"error_rate={summary['error_rate']:.2%}",
    f"p95_ms={summary['p95_ms']}",
    f"status={summary['status']}",
)
PY

echo "[reproduce] complete. Reports are in ./reports and the compose stack remains up."
