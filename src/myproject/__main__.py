"""``python -m myproject`` -> serve the FastAPI application."""

from __future__ import annotations

from myproject.api import _main

if __name__ == "__main__":
    raise SystemExit(_main())
