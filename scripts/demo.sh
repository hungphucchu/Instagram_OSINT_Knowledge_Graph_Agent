#!/usr/bin/env bash
# scripts/demo.sh
#
# End-to-end demo. Exercises every user story against the running app and
# prints PASS / FAIL per story. Intended to be run while `docker compose up`
# is running in another terminal.
#
# This is NOT the same as the user-story acceptance tests in
# tests/user_stories/. Those are pytest tests run during `make test`. This
# demo hits the live application from the outside, the same way the TA will
# during the manual walkthrough.

set -uo pipefail

APP_URL="${APP_URL:-http://localhost:8080}"
PASSED=0
FAILED=0
TOTAL=0

if ! curl -sf -o /dev/null --max-time 5 "$APP_URL/health"; then
  echo "ERROR: app is not reachable at $APP_URL/health" >&2
  echo "Start the app first: docker compose up" >&2
  exit 1
fi

echo "=================================================================="
echo "Demo run against $APP_URL"
echo "=================================================================="

run_story() {
  local id="$1"
  local description="$2"
  local cmd="$3"
  TOTAL=$((TOTAL + 1))
  echo
  echo "--- $id: $description ---"
  if eval "$cmd"; then
    echo "[$id] PASS"
    PASSED=$((PASSED + 1))
  else
    echo "[$id] FAIL"
    FAILED=$((FAILED + 1))
  fi
}

# US-01: happy-path query returns answer + citations
run_story "US-01" \
  "Submit a question; expect non-empty answer and citations" \
  "curl -sf -X POST $APP_URL/api/query -H 'Content-Type: application/json' \
        -d '{\"text\":\"Who appeared together most often?\",\"max_results\":5}' \
        | python3 -c 'import json,sys; d=json.load(sys.stdin); \
                      assert d.get(\"answer\"), \"empty answer\"; \
                      assert isinstance(d.get(\"citations\"), list), \"missing citations\"; \
                      print(\"answer-len=\", len(d[\"answer\"]), \"citations=\", len(d[\"citations\"]))'"

# US-02 [ERROR PATH]: empty input -> 400 with structured error
run_story "US-02" \
  "Empty input returns 400 with 'input text is required'" \
  "code=\$(curl -s -o /tmp/_us02.json -w '%{http_code}' -X POST $APP_URL/api/query \
        -H 'Content-Type: application/json' -d '{\"text\":\"\"}'); \
   test \"\$code\" = '400' && grep -q 'input text is required' /tmp/_us02.json"

# US-03 [ERROR PATH]: missing key -> 503. Skipped unless QUERY_LLM_API_KEY is unset.
if [[ -z "${QUERY_LLM_API_KEY:-}" ]]; then
  run_story "US-03" \
    "Missing LLM credential returns 503 with operator-readable error" \
    "code=\$(curl -s -o /tmp/_us03.json -w '%{http_code}' -X POST $APP_URL/api/query \
          -H 'Content-Type: application/json' -d '{\"text\":\"hello\"}'); \
     test \"\$code\" = '503' && grep -q 'not configured' /tmp/_us03.json"
else
  echo
  echo "--- US-03: skipped (QUERY_LLM_API_KEY is set; unset it to test the 503 path) ---"
fi

# US-04: sample pipeline returns counts
run_story "US-04" \
  "Sample pipeline returns raw_artifacts/extraction_records/dedup_clusters" \
  "curl -sf -X POST $APP_URL/api/pipeline/sample \
        | python3 -c 'import json,sys; d=json.load(sys.stdin); \
                      assert all(k in d for k in (\"run_id\",\"raw_artifacts\",\"extraction_records\",\"dedup_clusters\")), d; \
                      print(d)'"

# US-05: graph stats endpoint returns ints
run_story "US-05" \
  "Graph stats returns nodes/edges integers" \
  "curl -sf $APP_URL/api/stats \
        | python3 -c 'import json,sys; d=json.load(sys.stdin); \
                      assert isinstance(d.get(\"nodes\"), int) and isinstance(d.get(\"edges\"), int), d; \
                      print(d)'"

echo
echo "=================================================================="
echo "Demo summary: $PASSED / $TOTAL stories passed ($FAILED failed)"
echo "=================================================================="

[[ $FAILED -eq 0 ]]
