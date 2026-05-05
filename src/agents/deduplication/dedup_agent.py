"""Deduplication agent for Phase 3."""

from __future__ import annotations

import hashlib
import math
import re
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone

from agents.deduplication.dedup_store import DedupStore
from agents.deduplication.models import (
    DedupAuditEntry,
    DedupCluster,
    DedupMention,
    DedupPairScore,
    DedupReport,
    DedupRunResult,
    DedupThresholds,
)
from agents.extraction.extraction_store import ExtractionStore


@dataclass
class _UnionFind:
    parent: dict[str, str]

    def find(self, x: str) -> str:
        p = self.parent.setdefault(x, x)
        if p != x:
            self.parent[x] = self.find(p)
        return self.parent[x]

    def union(self, a: str, b: str) -> None:
        ra = self.find(a)
        rb = self.find(b)
        if ra != rb:
            self.parent[rb] = ra


class DedupAgent:
    """Runs deterministic dedup over extraction records in one run."""

    def __init__(
        self,
        *,
        extraction_store: ExtractionStore,
        dedup_store: DedupStore,
        embedding_backend: str,
        fuzzy_merge_threshold: float,
        embedding_merge_threshold: float,
        fuzzy_review_threshold: float,
        char_ngram_n: int,
    ) -> None:
        self._extraction_store = extraction_store
        self._dedup_store = dedup_store
        self._embedding_backend = embedding_backend
        self._fuzzy_merge_threshold = fuzzy_merge_threshold
        self._embedding_merge_threshold = embedding_merge_threshold
        self._fuzzy_review_threshold = fuzzy_review_threshold
        self._char_ngram_n = max(2, char_ngram_n)

    def run(self, *, run_id: str) -> DedupRunResult:
        started_at = datetime.now(timezone.utc)
        try:
            records = self._extraction_store.list_by_run(run_id)
            report = self._build_report(run_id=run_id, records=records)
            written = self._dedup_store.upsert_report(report)
            status = "completed" if records else "partial"
            error_message = None
        except Exception as exc:
            written = 0
            status = "failed"
            error_message = str(exc)
        finished_at = datetime.now(timezone.utc)
        return DedupRunResult(
            run_id=run_id,
            status=status,
            clusters_written=written,
            started_at=started_at,
            finished_at=finished_at,
            embedding_backend=self._embedding_backend,
            error_message=error_message,
        )

    def _build_report(self, *, run_id: str, records: list) -> DedupReport:
        mentions = self._collect_mentions(records)
        uf = _UnionFind(parent={x.mention_id: x.mention_id for x in mentions})
        pair_scores: list[DedupPairScore] = []
        audit_log: list[DedupAuditEntry] = []
        by_block = defaultdict(list)
        for mention in mentions:
            by_block[self._blocking_key(mention.normalized)].append(mention)

        for group in by_block.values():
            for idx in range(len(group)):
                for jdx in range(idx + 1, len(group)):
                    a = group[idx]
                    b = group[jdx]
                    fuzzy = self._fuzzy_score(a.normalized, b.normalized)
                    emb = self._embedding_score(a.normalized, b.normalized)
                    merged, rationale = self._decision(fuzzy=fuzzy, embedding=emb)
                    pair_scores.append(
                        DedupPairScore(
                            mention_id_a=a.mention_id,
                            mention_id_b=b.mention_id,
                            surface_a=a.surface_form,
                            surface_b=b.surface_form,
                            fuzzy_score=fuzzy,
                            embedding_score=emb,
                            merged=merged,
                            rationale=rationale,
                        )
                    )
                    action = "rejected"
                    if merged:
                        uf.union(a.mention_id, b.mention_id)
                        action = "merged"
                    elif rationale == "human_review":
                        action = "review"
                    audit_log.append(
                        DedupAuditEntry(
                            timestamp=datetime.now(timezone.utc),
                            mention_id_a=a.mention_id,
                            mention_id_b=b.mention_id,
                            action=action,
                            rationale=rationale,
                            fuzzy_score=fuzzy,
                            embedding_score=emb,
                        )
                    )

        clusters = self._clusters_from_union_find(mentions=mentions, uf=uf)
        return DedupReport(
            run_id=run_id,
            embedding_backend=self._embedding_backend,
            thresholds_used=DedupThresholds(
                fuzzy_merge=self._fuzzy_merge_threshold,
                embedding_merge=self._embedding_merge_threshold,
                fuzzy_review=self._fuzzy_review_threshold,
            ),
            mention_count=len(mentions),
            clusters=clusters,
            pair_scores=pair_scores,
            audit_log=audit_log,
        )

    def _collect_mentions(self, records: list) -> list[DedupMention]:
        mentions: list[DedupMention] = []
        for record in records:
            for idx, ent in enumerate(record.entities):
                text = ent.surface_form.strip()
                if not text:
                    continue
                mentions.append(
                    DedupMention(
                        mention_id=f"{record.artifact_id}:e:{idx}",
                        artifact_id=record.artifact_id,
                        source="entity",
                        entity_type=ent.entity_type,
                        surface_form=text,
                        normalized=self._normalize(text),
                    )
                )
            for idx, rel in enumerate(record.relations):
                subject = rel.subject.strip()
                if subject:
                    mentions.append(
                        DedupMention(
                            mention_id=f"{record.artifact_id}:r:{idx}:s",
                            artifact_id=record.artifact_id,
                            source="relation_subject",
                            entity_type="UNKNOWN",
                            surface_form=subject,
                            normalized=self._normalize(subject),
                        )
                    )
                obj = rel.object.strip()
                if obj:
                    mentions.append(
                        DedupMention(
                            mention_id=f"{record.artifact_id}:r:{idx}:o",
                            artifact_id=record.artifact_id,
                            source="relation_object",
                            entity_type="UNKNOWN",
                            surface_form=obj,
                            normalized=self._normalize(obj),
                        )
                    )
        return [x for x in mentions if x.normalized]

    @staticmethod
    def _normalize(text: str) -> str:
        out = text.lower().strip()
        out = out.lstrip("@#")
        out = re.sub(r"[_\-]+", " ", out)
        out = re.sub(r"[^a-z0-9\s]", "", out)
        out = re.sub(r"\s+", " ", out).strip()
        return out

    @staticmethod
    def _blocking_key(normalized: str) -> str:
        if not normalized:
            return "empty"
        first = normalized.split(" ", 1)[0][:2]
        bucket = len(normalized) // 4
        return f"{first}:{bucket}"

    def _fuzzy_score(self, a: str, b: str) -> float:
        try:
            from rapidfuzz import fuzz  # type: ignore

            return float(fuzz.ratio(a, b)) / 100.0
        except Exception:
            # Deterministic fallback when RapidFuzz is not installed.
            from difflib import SequenceMatcher

            return SequenceMatcher(a=a, b=b).ratio()

    def _embedding_score(self, a: str, b: str) -> float | None:
        if self._embedding_backend == "off":
            return None
        va = self._char_ngram_vector(a)
        vb = self._char_ngram_vector(b)
        return self._cosine_similarity(va, vb)

    def _char_ngram_vector(self, text: str) -> dict[str, float]:
        padded = f"^{text}$"
        n = self._char_ngram_n
        if len(padded) < n:
            return {padded: 1.0}
        grams = [padded[idx : idx + n] for idx in range(len(padded) - n + 1)]
        counts = Counter(grams)
        total = float(sum(counts.values()) or 1.0)
        return {k: v / total for k, v in counts.items()}

    @staticmethod
    def _cosine_similarity(a: dict[str, float], b: dict[str, float]) -> float:
        dot = 0.0
        for key, value in a.items():
            dot += value * b.get(key, 0.0)
        norm_a = math.sqrt(sum(x * x for x in a.values()))
        norm_b = math.sqrt(sum(x * x for x in b.values()))
        if norm_a == 0.0 or norm_b == 0.0:
            return 0.0
        return dot / (norm_a * norm_b)

    def _decision(self, *, fuzzy: float, embedding: float | None) -> tuple[bool, str]:
        if fuzzy < self._fuzzy_review_threshold:
            return False, "rejected"
        if self._embedding_backend == "off":
            if fuzzy >= self._fuzzy_merge_threshold:
                return True, "fuzzy_only"
            return False, "human_review"
        if fuzzy >= self._fuzzy_merge_threshold and (embedding or 0.0) >= self._embedding_merge_threshold:
            return True, "embedding_confirmed"
        return False, "human_review"

    @staticmethod
    def _clusters_from_union_find(*, mentions: list[DedupMention], uf: _UnionFind) -> list[DedupCluster]:
        buckets: dict[str, list[DedupMention]] = defaultdict(list)
        for mention in mentions:
            buckets[uf.find(mention.mention_id)].append(mention)
        clusters: list[DedupCluster] = []
        for group in buckets.values():
            aliases = sorted({x.surface_form for x in group})
            normalized = sorted({x.normalized for x in group})
            canonical_norm = normalized[0] if normalized else ""
            canonical_surface = DedupAgent._pick_canonical_surface(group)
            digest = hashlib.sha1(canonical_norm.encode("utf-8")).hexdigest()[:16]
            canonical_id = f"ent_{digest}"
            mention_ids = sorted(x.mention_id for x in group)
            clusters.append(
                DedupCluster(
                    canonical_id=canonical_id,
                    canonical_surface=canonical_surface,
                    aliases=aliases,
                    mention_ids=mention_ids,
                )
            )
        clusters.sort(key=lambda x: x.canonical_id)
        return clusters

    @staticmethod
    def _pick_canonical_surface(group: list[DedupMention]) -> str:
        counts = Counter(x.surface_form for x in group)
        best = sorted(counts.items(), key=lambda x: (-x[1], len(x[0]), x[0]))[0]
        return best[0]
