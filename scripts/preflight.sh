#!/usr/bin/env bash
# scripts/preflight.sh
#
# Local grading dry-run. Runs every automated check the reviewer will run, in the
# same order. If preflight passes, your automated grade will pass. The manual
# walkthrough (Phase 3 in the rubric) cannot be simulated here; you still need
# to demo your app yourself or have a teammate walk through STORIES.md.
#
# Exit code 0 = all automated checks passed.
# Non-zero exit code = at least one check failed; fix it before pushing.

set -uo pipefail
# Deliberately not using `set -e` so every check runs and the summary is
# accurate; we exit non-zero at the end if anything failed.

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"
mkdir -p reports

FAILED_CHECKS=()

fail_early() {
  echo
  echo "=================================================================="
  echo "[preflight] ERROR: $1"
  echo "=================================================================="
  echo "[preflight] $2"
  exit 2
}

# ---------------------------------------------------------------------------
# Prerequisites (fail fast with actionable guidance)
# ---------------------------------------------------------------------------
if ! command -v docker >/dev/null 2>&1; then
  fail_early \
    "Docker CLI not found." \
    "Install Docker Desktop (or Docker Engine) and rerun scripts/preflight.sh."
fi

if ! docker compose version >/dev/null 2>&1; then
  fail_early \
    "Docker Compose is not available." \
    "Install/enable Docker Compose plugin and rerun scripts/preflight.sh."
fi

if ! docker info >/dev/null 2>&1; then
  fail_early \
    "Docker daemon is not running." \
    "Start Docker Desktop (or system Docker service), then rerun scripts/preflight.sh."
fi

run_check() {
  local name="$1"; shift
  local log
  local pid
  local rc
  local elapsed
  log="$(mktemp)"
  echo
  echo "=================================================================="
  echo "[preflight] $name"
  echo "=================================================================="
  "$@" >"$log" 2>&1 &
  pid=$!
  elapsed=0
  while kill -0 "$pid" 2>/dev/null; do
    echo "[preflight] $name still running... ${elapsed}s elapsed"
    sleep 5
    elapsed=$((elapsed + 5))
  done
  wait "$pid"
  rc=$?

  if [[ "$rc" -eq 0 ]]; then
    # Normalize carriage-return based progress output and strip ANSI escapes.
    python3 - "$log" <<'PYEOF'
import re
import sys
from pathlib import Path

path = Path(sys.argv[1])
text = path.read_bytes().decode("utf-8", errors="replace")
text = text.replace("\r", "\n")
text = re.sub(r"\x1b\[[0-9;?]*[ -/]*[@-~]", "", text)
for line in text.splitlines():
    print(line.rstrip())
PYEOF
    rm -f "$log"
    echo "[preflight] PASS: $name"
  else
    python3 - "$log" <<'PYEOF'
import re
import sys
from pathlib import Path

path = Path(sys.argv[1])
text = path.read_bytes().decode("utf-8", errors="replace")
text = text.replace("\r", "\n")
text = re.sub(r"\x1b\[[0-9;?]*[ -/]*[@-~]", "", text)
for line in text.splitlines():
    print(line.rstrip())
PYEOF
    rm -f "$log"
    echo "[preflight] FAIL: $name"
    FAILED_CHECKS+=("$name")
  fi
}

ensure_app_ready() {
  # Bring the stack up if app is missing/stopped, then wait for health.
  if [[ "$(docker compose ps -q app 2>/dev/null)" == "" ]]; then
    echo "[preflight] app service is not running; starting compose stack..."
    docker compose up -d
  fi
  if ! docker compose ps --format json 2>/dev/null | grep -q '"Service":"app".*"State":"running"'; then
    echo "[preflight] app service is not running; starting compose stack..."
    docker compose up -d
  fi

  for _ in $(seq 1 60); do
    if curl -fsS "http://localhost:${APP_PORT:-8080}/health" >/dev/null 2>&1; then
      return 0
    fi
    sleep 2
  done
  echo "[preflight] app did not become healthy in time."
  docker compose ps
  return 1
}

run_make_test() {
  ensure_app_ready && docker compose exec -T app make test
}

run_make_lint() {
  ensure_app_ready && docker compose exec -T app make lint
}

run_pip_audit() {
  ensure_app_ready && docker compose exec -T app sh -lc \
    "pip-audit -r requirements.txt --desc 2>&1 | tee reports/security.txt; \
     ! grep -E 'Critical|High' reports/security.txt"
}

run_make_loadtest() {
  ensure_app_ready && docker compose exec -T app make loadtest
}

# ---------------------------------------------------------------------------
# Phase 1: Automated checks
# ---------------------------------------------------------------------------
run_check "make reproduce (full pipeline replay)" \
  make reproduce

run_check "make test (unit + integration + user_stories + edge)" \
  run_make_test

# Persist `make test` exit code for the grading script.
echo $? > reports/make_test_exit.txt

run_check "make lint (ruff + black --check + mypy)" \
  run_make_lint
echo $? > reports/lint_exit.txt

run_check "pip-audit (dependency vulnerabilities)" \
  run_pip_audit

run_check "make loadtest (sustained throughput, error rate)" \
  run_make_loadtest

# Spec regeneration is optional locally (requires ANTHROPIC_API_KEY) but is the
# largest single rubric category, so we run it when the key is present.
if [[ -n "${ANTHROPIC_API_KEY:-}" ]]; then
  run_check "scripts/regenerate.sh (spec → code regeneration)" \
    bash scripts/regenerate.sh
else
  echo
  echo "=================================================================="
  echo "[preflight] SKIP: scripts/regenerate.sh (set ANTHROPIC_API_KEY to enable)"
  echo "=================================================================="
fi

# ---------------------------------------------------------------------------
# Phase 2: Build environment sanity (compose + env example exist; YAML valid)
# ---------------------------------------------------------------------------
run_check "Compose configuration sanity" \
  bash -c "test -f docker-compose.yml && test -f .env.example && \
           docker compose config -q 2>&1"

# ---------------------------------------------------------------------------
# Team Contributions check — git shortlog snapshot
# ---------------------------------------------------------------------------
run_check "git contributions snapshot" \
  bash -c "git shortlog -sne --all --no-merges > reports/git_contributions.txt && \
           cat reports/git_contributions.txt"

# ---------------------------------------------------------------------------
# Final report
# ---------------------------------------------------------------------------
echo
echo "=================================================================="
echo "[preflight] SUMMARY"
echo "=================================================================="
if [[ ${#FAILED_CHECKS[@]} -eq 0 ]]; then
  echo "[preflight] ALL AUTOMATED CHECKS PASSED."
  echo "[preflight] You are ready to push for grading."
  echo "[preflight] Reminder: Phase 3 of grading is a manual walkthrough of"
  echo "[preflight] docs/STORIES.md against your running app. Make sure every"
  echo "[preflight] story works against docker compose up before submitting."
  exit 0
else
  echo "[preflight] FAILED CHECKS:"
  for c in "${FAILED_CHECKS[@]}"; do
    echo "  - $c"
  done
  echo
  echo "[preflight] Fix each failure above before pushing."
  exit 1
fi
