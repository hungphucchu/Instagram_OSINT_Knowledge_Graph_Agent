"""Read-only Cypher verifier and normalizer."""

from __future__ import annotations

import re

_BLOCKED = re.compile(r"\b(CREATE|DELETE|DETACH|MERGE|SET|REMOVE|DROP|CALL|LOAD\s+CSV)\b", re.IGNORECASE)
_HAS_MATCH_OR_WITH = re.compile(r"\b(MATCH|WITH)\b", re.IGNORECASE)
_HAS_RETURN = re.compile(r"\bRETURN\b", re.IGNORECASE)
_HAS_LIMIT = re.compile(r"\bLIMIT\s+\d+\b", re.IGNORECASE)
_MALFORMED_RETURN = re.compile(r"\bRETURN\s*(?:$|LIMIT\b)", re.IGNORECASE)


def verify_read_only_cypher(query: str, *, max_limit: int) -> tuple[bool, str, str | None]:
    q = (query or "").strip().rstrip(";")
    if not q:
        return False, "", "empty query"
    if _BLOCKED.search(q):
        return False, q, "mutating clause detected"
    if not _HAS_MATCH_OR_WITH.search(q) or not _HAS_RETURN.search(q):
        return False, q, "query must include MATCH/WITH and RETURN"
    if _MALFORMED_RETURN.search(q):
        return False, q, "malformed RETURN clause"
    normalized = _enforce_limit(q, max_limit=max_limit)
    return True, normalized, None


def _enforce_limit(query: str, *, max_limit: int) -> str:
    if not _HAS_LIMIT.search(query):
        return f"{query} LIMIT {max_limit}"
    m = re.search(r"\bLIMIT\s+(\d+)\b", query, flags=re.IGNORECASE)
    if not m:
        return f"{query} LIMIT {max_limit}"
    current = int(m.group(1))
    if current <= max_limit:
        return query
    return re.sub(r"\bLIMIT\s+\d+\b", f"LIMIT {max_limit}", query, flags=re.IGNORECASE)

