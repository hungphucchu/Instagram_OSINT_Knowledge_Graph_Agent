"""Detect when a collected post is unchanged vs the latest stored version."""

from __future__ import annotations

import hashlib
import json
import re

from schemas.raw_artifact import RawArtifact


def raw_post_fingerprint(artifact: RawArtifact) -> str:
    """Hash caption, tags, mentions, and canonical raw JSON (order-independent)."""
    payload = json.dumps(artifact.raw_payload, sort_keys=True, separators=(",", ":"), default=str)
    norm = {
        "caption": artifact.caption_text,
        "hashtags": sorted(artifact.hashtags),
        "mentions": sorted(artifact.mentions),
        "raw": payload,
    }
    canonical = json.dumps(norm, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def stable_artifact_id(artifact: RawArtifact, content_fp: str) -> str:
    """Artifact id keyed by adapter + post identity + content (not pipeline run_id)."""
    h = hashlib.sha256(
        f"{artifact.adapter_id}:{artifact.platform_post_id}:{artifact.source_url}:{content_fp}".encode()
    ).hexdigest()[:24]
    safe = re.sub(r"[^0-9A-Za-z_]+", "_", artifact.adapter_id).strip("_")[:12] or "src"
    return f"{safe}-{h}"
