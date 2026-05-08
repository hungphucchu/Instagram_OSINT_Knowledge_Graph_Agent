#!/usr/bin/env python3
"""Print clean one-line summaries from test/coverage XML reports."""

from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path


def counts(path: str) -> tuple[int, int, int, int]:
    root = ET.parse(path).getroot()
    suites = root.findall("testsuite") if root.tag == "testsuites" else [root]
    total = sum(int(s.get("tests", 0)) for s in suites)
    failed = sum(int(s.get("failures", 0)) + int(s.get("errors", 0)) for s in suites)
    skipped = sum(int(s.get("skipped", 0)) for s in suites)
    passed = total - failed - skipped
    return total, passed, failed, skipped


def main() -> int:
    unit = counts("reports/unit.xml")
    integration = counts("reports/integration.xml")
    user_stories = counts("reports/user_stories.xml")
    edge = counts("reports/edge.xml")

    print(f"[test] unit: passed={unit[1]}/{unit[0]} failed={unit[2]} skipped={unit[3]}")
    print(
        f"[test] integration: passed={integration[1]}/{integration[0]} "
        f"failed={integration[2]} skipped={integration[3]}"
    )
    print(
        f"[test] user_stories: passed={user_stories[1]}/{user_stories[0]} "
        f"failed={user_stories[2]} skipped={user_stories[3]}"
    )
    print(f"[test] edge: passed={edge[1]}/{edge[0]} failed={edge[2]} skipped={edge[3]}")

    coverage_path = Path("reports/coverage.xml")
    cov = ET.parse(coverage_path).getroot()
    line_rate = float(cov.get("line-rate", "0"))
    print(f"[test] coverage: line_rate={line_rate:.2%}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

