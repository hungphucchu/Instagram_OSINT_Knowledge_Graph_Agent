#!/usr/bin/env bash
# scripts/preflight.sh
#
# Local grading dry-run. Runs every automated check the TA will run, in the
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

run_check() {
  local name="$1"; shift
  echo
  echo "=================================================================="
  echo "[preflight] $name"
  echo "=================================================================="
  if "$@"; then
    echo "[preflight] PASS: $name"
  else
    echo "[preflight] FAIL: $name"
    FAILED_CHECKS+=("$name")
  fi
}

# ---------------------------------------------------------------------------
# Phase 1: Automated checks
# ---------------------------------------------------------------------------
run_check "make reproduce (full pipeline replay)" \
  make reproduce

run_check "make test (unit + integration + user_stories + edge)" \
  make test

# Persist `make test` exit code for the grading script.
echo $? > reports/make_test_exit.txt

run_check "make lint (ruff + black --check + mypy)" \
  make lint
echo $? > reports/lint_exit.txt

run_check "pip-audit (dependency vulnerabilities)" \
  bash -c "pip-audit -r requirements.txt --desc 2>&1 | tee reports/security.txt; \
           ! grep -E 'Critical|High' reports/security.txt"

run_check "make loadtest (sustained throughput, error rate)" \
  make loadtest

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
