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
  | tee reports/reproduce_pipeline.json

echo "[reproduce] running full test suite in the app container"
docker compose exec -T app sh -lc \
  'mkdir -p reports && \
   PYTHONPATH=src pytest tests/unit --junitxml=reports/unit.xml && \
   PYTHONPATH=src pytest tests/integration --junitxml=reports/integration.xml && \
   PYTHONPATH=src pytest tests/user_stories --junitxml=reports/user_stories.xml && \
   PYTHONPATH=src pytest tests/edge --junitxml=reports/edge.xml && \
   PYTHONPATH=src pytest --cov=myproject \
      --cov-report=xml:reports/coverage.xml \
      --cov-report=html:reports/coverage_html \
      --cov-fail-under=70 \
      tests/unit tests/integration tests/user_stories'

echo "[reproduce] running load test to regenerate README headline numbers"
docker compose exec -T app sh -lc \
  'mkdir -p reports && \
   locust -f tests/load/locustfile.py \
     --headless -u 20 -r 5 -t 60s \
     --host=http://localhost:8080 \
     --csv=reports/loadtest && \
   PYTHONPATH=src python scripts/summarize_loadtest.py'

echo "[reproduce] complete. Reports are in ./reports and the compose stack remains up."
