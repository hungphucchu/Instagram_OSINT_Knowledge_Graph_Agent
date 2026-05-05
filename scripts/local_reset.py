#!/usr/bin/env python3
"""Dev: full local reset — same as `python -m cli local-reset --yes`.

Removes SQLite files for collection / extraction / dedup (paths from `.env`)
and runs `MATCH (n) DETACH DELETE n` on the configured Neo4j database.

Usage:

  PYTHONPATH=src python scripts/local_reset.py --yes
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


def main() -> int:
    repo = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(repo / "src"))

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--yes", action="store_true", help="required")
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args()

    from cli.dev_reset import run_local_reset

    if not args.yes:
        print("error: pass --yes to confirm full local reset", file=sys.stderr)
        return 1
    return run_local_reset(verbose=args.verbose)


if __name__ == "__main__":
    raise SystemExit(main())
