# Makefile for the Instagram OSINT Knowledge Graph Agent (CS 6263 final project).
#
# Every target here is referenced by the rubric. The reviewer runs these targets
# during grading. Do not rename them.
#
# Conventions:
#   * Targets that the reviewer runs are .PHONY
#   * All long-running targets emit reports under reports/

.PHONY: help install install-dev test test-unit test-integration test-user-stories test-edge \
        lint format reproduce loadtest demo \
        download-data download-models \
        clean preflight regenerate run health stop \
        web-install web-dev

PYTHON  ?= python3
PIP     ?= pip
PYTEST  ?= pytest
PACKAGE := myproject
SRC     := src/$(PACKAGE)

# ---------------------------------------------------------------------------
help:
	@echo "Common targets:"
	@echo "  make install         install runtime dependencies"
	@echo "  make install-dev     install runtime + test/lint dependencies"
	@echo "  make test            run unit + integration + user-story + edge suites + coverage"
	@echo "  make lint            ruff + black --check + mypy on src/myproject and tests/"
	@echo "  make format          apply ruff --fix + black"
	@echo "  make reproduce       full Docker-backed replay: rebuild stack, run pipeline, tests, loadtest"
	@echo "  make loadtest        run the Locust load test against the live app"
	@echo "  make demo            exercise every user story against the live app"
	@echo "  make download-data   stage fixture data into data/ (no network needed)"
	@echo "  make download-models models are API-hosted; this just records provenance"
	@echo "  make regenerate      regenerate src/myproject/ from docs/SPEC.md via LLM"
	@echo "  make preflight       run every automated grading check locally"
	@echo "  make run             run the FastAPI app on \$$APP_PORT (default 8080)"
	@echo "  make clean           remove generated artifacts"

# ---------------------------------------------------------------------------
# Installation helpers — used in CI / Docker, not by the reviewer directly.
# ---------------------------------------------------------------------------
install:
	$(PIP) install -r requirements.txt

install-dev:
	$(PIP) install -e ".[dev]"

# ---------------------------------------------------------------------------
# Testing — JUnit XML + coverage are required by the rubric.
# ---------------------------------------------------------------------------
test: reports
	@printf '%s\n' "[test] running unit suite"
	@PYTHONPATH=src $(PYTEST) -q tests/unit \
	  --junitxml=reports/unit.xml \
	  > reports/unit.log 2>&1 || { cat reports/unit.log; exit 1; }
	@printf '%s\n' "[test] running integration suite"
	@PYTHONPATH=src $(PYTEST) -q tests/integration \
	  --junitxml=reports/integration.xml \
	  > reports/integration.log 2>&1 || { cat reports/integration.log; exit 1; }
	@printf '%s\n' "[test] running user_stories suite"
	@PYTHONPATH=src $(PYTEST) -q tests/user_stories \
	  --junitxml=reports/user_stories.xml \
	  > reports/user_stories.log 2>&1 || { cat reports/user_stories.log; exit 1; }
	@printf '%s\n' "[test] running edge suite"
	@PYTHONPATH=src $(PYTEST) -q tests/edge \
	  --junitxml=reports/edge.xml \
	  > reports/edge.log 2>&1 || { cat reports/edge.log; exit 1; }
	@printf '%s\n' "[test] running coverage suite"
	@PYTHONPATH=src $(PYTEST) -q --cov=$(PACKAGE) \
	  --cov-report=xml:reports/coverage.xml \
	  --cov-report=html:reports/coverage_html \
	  --cov-fail-under=70 \
	  tests/unit tests/integration tests/user_stories \
	  > reports/coverage_test.log 2>&1 || { cat reports/coverage_test.log; exit 1; }
	@PYTHONPATH=src $(PYTHON) scripts/summarize_test_reports.py

test-unit: reports
	@PYTHONPATH=src $(PYTEST) tests/unit --junitxml=reports/unit.xml

test-integration: reports
	@PYTHONPATH=src $(PYTEST) tests/integration --junitxml=reports/integration.xml

test-user-stories: reports
	@PYTHONPATH=src $(PYTEST) tests/user_stories --junitxml=reports/user_stories.xml

test-edge: reports
	@PYTHONPATH=src $(PYTEST) tests/edge --junitxml=reports/edge.xml

# ---------------------------------------------------------------------------
# Lint / format / static checks
# ---------------------------------------------------------------------------
lint:
	ruff check $(SRC) tests/
	black --check $(SRC) tests/
	mypy $(SRC)

format:
	ruff check --fix $(SRC) tests/
	black $(SRC) tests/

# ---------------------------------------------------------------------------
# Reproduce: full clean replay (rubric: Reproducibility Manifest, 10 pts)
# ---------------------------------------------------------------------------
reproduce: reports
	bash scripts/reproduce.sh

# ---------------------------------------------------------------------------
# Data and model fetch — pinned in docs/DATA.md and docs/MODELS.md
# ---------------------------------------------------------------------------
download-data:
	@echo "[download-data] using bundled fixtures (no external network required)"
	@mkdir -p data
	@cp -f fixtures/raw_artifacts.json data/raw_artifacts.json
	@echo "[download-data] staged fixtures/raw_artifacts.json -> data/raw_artifacts.json"

download-models:
	@echo "[download-models] all models are API-hosted; nothing to download"
	@mkdir -p reports
	@printf '%s\n' \
	  'All application models are API-hosted. No local checkpoint download is required.' \
	  'Replay mode disables the query LLM (`QUERY_LLM_ENABLED=false`) so the' \
	  'headline endpoint can be exercised deterministically without paid inference.' \
	  'See docs/MODELS.md and grading/manifest.yaml for pinned model provenance.' \
	  > reports/download_models.txt
	@echo "[download-models] wrote reports/download_models.txt"

# ---------------------------------------------------------------------------
# Stress and load (rubric: Stress and Robustness, 6 pts)
# ---------------------------------------------------------------------------
loadtest: reports
	@echo "[loadtest] requires the app to be running (docker compose up)"
	@sh -c 'set -e; \
	  rm -f reports/loadtest.log; \
	  locust -f tests/load/locustfile.py \
	    --headless --only-summary -u 20 -r 5 -t 60s \
	    --host=$${APP_URL:-http://localhost:8080} \
	    --csv=reports/loadtest \
	    > reports/loadtest.log 2>&1 & \
	  pid=$$!; \
	  elapsed=0; \
	  trap "kill $$pid 2>/dev/null || true" INT TERM; \
	  echo "[loadtest] started (expected duration: about 60 seconds)"; \
	  while kill -0 $$pid 2>/dev/null; do \
	    echo "[loadtest] still running... $${elapsed}s elapsed"; \
	    sleep 5; \
	    elapsed=$$((elapsed + 5)); \
	  done; \
	  wait $$pid || { cat reports/loadtest.log; exit 1; }'
	@PYTHONPATH=src $(PYTHON) scripts/summarize_loadtest.py --quiet
	@$(PYTHON) -c "import json, pathlib; s = json.loads(pathlib.Path('reports/benchmarks.json').read_text())['summary']; print('[loadtest] summary:', 'rps={:.2f}'.format(s['requests_per_second']), 'error_rate={:.2%}'.format(s['error_rate']), 'p95_ms={}'.format(s['p95_ms']), 'status={}'.format(s['status']))"

# ---------------------------------------------------------------------------
# Demo and regeneration
# ---------------------------------------------------------------------------
demo:
	bash scripts/demo.sh

regenerate:
	bash scripts/regenerate.sh

preflight:
	bash scripts/preflight.sh

# ---------------------------------------------------------------------------
# Run the app locally without Docker (for quick iteration)
# ---------------------------------------------------------------------------
run:
	PYTHONPATH=src APP_PORT=$${APP_PORT:-8080} $(PYTHON) -m $(PACKAGE).api

health:
	@curl -fsS http://localhost:$${APP_PORT:-8080}/health || (echo "app not healthy" && exit 1)

stop:
	docker compose down

# ---------------------------------------------------------------------------
# Optional Next.js front-end (kept for the project demo; not graded)
# ---------------------------------------------------------------------------
web-install:
	cd web && npm install

web-dev:
	cd web && npm run dev

# ---------------------------------------------------------------------------
# Housekeeping
# ---------------------------------------------------------------------------
reports:
	@mkdir -p reports

clean:
	rm -rf reports regenerated .pytest_cache .ruff_cache .mypy_cache
	find . -type d -name __pycache__ -exec rm -rf {} +
