"""Run identifiers for structured logging (no secrets)."""

from __future__ import annotations

import uuid


def new_run_id() -> str:
    """Return a new UUID string for a pipeline or CLI run."""
    return str(uuid.uuid4())
