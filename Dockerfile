# Multi-stage build. Final image runs as a non-root user.

# ---------------------------------------------------------------------------
# Builder stage — compile wheels for every pinned dependency
# ---------------------------------------------------------------------------
FROM python:3.11.9-slim-bookworm AS builder

WORKDIR /build
COPY requirements.txt ./
RUN pip install --upgrade pip \
 && pip wheel --wheel-dir=/wheels -r requirements.txt

# ---------------------------------------------------------------------------
# Runtime stage
# ---------------------------------------------------------------------------
FROM python:3.11.9-slim-bookworm

# Non-root user (rubric requirement)
RUN useradd -m -u 1000 -s /bin/bash app
USER app
WORKDIR /home/app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH=/home/app/.local/bin:$PATH

# Install pinned wheels, then the project itself in editable mode.
COPY --from=builder /wheels /wheels
COPY --chown=app:app requirements.txt ./
RUN pip install --user --no-index --find-links=/wheels -r requirements.txt

COPY --chown=app:app pyproject.toml README.md ./
COPY --chown=app:app src ./src
COPY --chown=app:app fixtures ./fixtures
COPY --chown=app:app scripts ./scripts
COPY --chown=app:app docs ./docs
COPY --chown=app:app grading ./grading
COPY --chown=app:app tests ./tests
COPY --chown=app:app Makefile ./
RUN pip install --user -e .

EXPOSE 8080

# Health endpoint must respond 200; docker-compose health check uses this
HEALTHCHECK --interval=10s --timeout=5s --start-period=15s --retries=3 \
  CMD python -c "import urllib.request,sys; \
    sys.exit(0) if urllib.request.urlopen('http://localhost:8080/health', timeout=3).status == 200 else sys.exit(1)" \
  || exit 1

CMD ["python", "-m", "uvicorn", "myproject.api:app", "--host", "0.0.0.0", "--port", "8080"]
