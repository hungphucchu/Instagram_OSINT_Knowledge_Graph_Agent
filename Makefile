# Makefile for the Instagram OSINT Knowledge Graph Agent (CS 6263 final project).
#
# Every target here is referenced by the rubric. The TA runs these targets
# during grading. Do not rename them.
#
# Conventions:
#   * Targets that the TA runs are .PHONY
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
# Installation helpers — used in CI / Docker, not by the TA directly.
# ---------------------------------------------------------------------------
install:
	$(PIP) install -r requirements.txt

install-dev:
	$(PIP) install -e ".[dev]"

# ---------------------------------------------------------------------------
# Testing — JUnit XML + coverage are required by the rubric.
# ---------------------------------------------------------------------------
test: reports
	PYTHONPATH=src $(PYTEST) tests/unit \
	  --junitxml=reports/unit.xml
	PYTHONPATH=src $(PYTEST) tests/integration \
	  --junitxml=reports/integration.xml
	PYTHONPATH=src $(PYTEST) tests/user_stories \
	  --junitxml=reports/user_stories.xml
	PYTHONPATH=src $(PYTEST) tests/edge \
	  --junitxml=reports/edge.xml
	PYTHONPATH=src $(PYTEST) --cov=$(PACKAGE) \
	          --cov-report=xml:reports/coverage.xml \
	          --cov-report=html:reports/coverage_html \
	          --cov-fail-under=70 \
	          tests/unit tests/integration tests/user_stories

test-unit: reports
	PYTHONPATH=src $(PYTEST) tests/unit --junitxml=reports/unit.xml

test-integration: reports
	PYTHONPATH=src $(PYTEST) tests/integration --junitxml=reports/integration.xml

test-user-stories: reports
	PYTHONPATH=src $(PYTEST) tests/user_stories --junitxml=reports/user_stories.xml

test-edge: reports
	PYTHONPATH=src $(PYTEST) tests/edge --junitxml=reports/edge.xml

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
	locust -f tests/load/locustfile.py \
	  --headless -u 20 -r 5 -t 60s \
	  --host=$${APP_URL:-http://localhost:8080} \
	  --csv=reports/loadtest
	PYTHONPATH=src $(PYTHON) scripts/summarize_loadtest.py

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
