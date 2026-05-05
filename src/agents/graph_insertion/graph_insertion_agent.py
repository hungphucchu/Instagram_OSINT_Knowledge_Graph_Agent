"""Graph insertion agent for Phase 4."""

from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone

from agents.collection.raw_artifact_store import RawArtifactStore
from agents.deduplication.dedup_store import DedupStore
from agents.extraction.extraction_store import ExtractionStore
from agents.graph_insertion.models import GraphInsertionRunResult


class GraphInsertionAgent:
    """Maps dedup + extraction records into graph nodes/relationships."""

    def __init__(
        self,
        *,
        graph_backend: str,
        graph_store: object,
        raw_store: RawArtifactStore,
        extraction_store: ExtractionStore,
        dedup_store: DedupStore,
    ) -> None:
        self._graph_backend = graph_backend
        self._graph_store = graph_store
        self._raw_store = raw_store
        self._extraction_store = extraction_store
        self._dedup_store = dedup_store

    def run(self, *, run_id: str) -> GraphInsertionRunResult:
        started_at = datetime.now(timezone.utc)
        created_nodes = 0
        updated_nodes = 0
        created_rels = 0
        updated_rels = 0
        try:
            if self._graph_backend != "neo4j":
                raise ValueError("GRAPH_BACKEND must be neo4j in current Phase 4 configuration")

            ensure_constraints = getattr(self._graph_store, "ensure_constraints", None)
            if callable(ensure_constraints):
                ensure_constraints()

            artifacts = {x.artifact_id: x for x in self._raw_store.list_by_run(run_id)}
            records = self._extraction_store.list_by_run(run_id)
            report = self._dedup_store.get_by_run(run_id)
            if report is None:
                raise ValueError(f"No dedup report found for run_id={run_id}")

            mention_map = self._build_mention_map(records)
            mention_to_canonical: dict[str, str] = {}

            for cluster in report.clusters:
                entity_kind = self._infer_entity_kind(cluster.mention_ids, mention_map)
                created = self._graph_store.upsert_node(
                    node_id=cluster.canonical_id,
                    label="CanonicalEntity",
                    properties={
                        "canonical_surface": cluster.canonical_surface,
                        "aliases": cluster.aliases,
                        "mention_ids": cluster.mention_ids,
                        "entity_kind": entity_kind,
                    },
                    source_run_id=run_id,
                )
                if created:
                    created_nodes += 1
                else:
                    updated_nodes += 1
                for mention_id in cluster.mention_ids:
                    mention_to_canonical[mention_id] = cluster.canonical_id

            for artifact in artifacts.values():
                post_node_id = f"post:{artifact.platform_post_id}"
                artifact_node_id = f"artifact:{artifact.artifact_id}"
                post_created = self._graph_store.upsert_node(
                    node_id=post_node_id,
                    label="Post",
                    properties={
                        "platform_post_id": artifact.platform_post_id,
                        "source_url": artifact.source_url,
                        "caption_text": artifact.caption_text,
                        "hashtags": artifact.hashtags,
                        "mentions": artifact.mentions,
                        "collected_at": artifact.collected_at.isoformat(),
                    },
                    source_run_id=run_id,
                )
                if post_created:
                    created_nodes += 1
                else:
                    updated_nodes += 1
                artifact_created = self._graph_store.upsert_node(
                    node_id=artifact_node_id,
                    label="Artifact",
                    properties={
                        "artifact_id": artifact.artifact_id,
                        "adapter_id": artifact.adapter_id,
                        "collector_version": artifact.collector_version,
                        # Neo4j properties must be primitives or arrays of primitives — no nested maps.
                        # Full `raw_payload` stays in SQLite (`raw_artifacts`); digest links for audit.
                        "raw_payload_digest": self._json_digest(artifact.raw_payload),
                    },
                    source_run_id=run_id,
                )
                if artifact_created:
                    created_nodes += 1
                else:
                    updated_nodes += 1

                sourced_created = self._graph_store.upsert_relationship(
                    rel_id=self._rel_id("SOURCED_FROM", post_node_id, artifact_node_id, run_id),
                    rel_type="SOURCED_FROM",
                    from_node_id=post_node_id,
                    to_node_id=artifact_node_id,
                    properties={"source_run_id": run_id},
                    source_run_id=run_id,
                )
                if sourced_created:
                    created_rels += 1
                else:
                    updated_rels += 1

            for record in records:
                artifact = artifacts.get(record.artifact_id)
                if artifact is None:
                    continue
                post_node_id = f"post:{artifact.platform_post_id}"
                for ridx, relation in enumerate(record.relations):
                    subject_mention = f"{record.artifact_id}:r:{ridx}:s"
                    object_mention = f"{record.artifact_id}:r:{ridx}:o"
                    subject_id = mention_to_canonical.get(subject_mention)
                    object_id = mention_to_canonical.get(object_mention)
                    if subject_id is None or object_id is None:
                        continue

                    rel_type = self._normalize_predicate(relation.predicate)
                    snip_hash = self._snippet_hash(relation.evidence_span or relation.predicate)
                    ee_created = self._graph_store.upsert_relationship(
                        rel_id=self._rel_id(
                            rel_type,
                            subject_id,
                            object_id,
                            record.artifact_id,
                            str(ridx),
                        ),
                        rel_type=rel_type,
                        from_node_id=subject_id,
                        to_node_id=object_id,
                        properties={
                            "artifact_id": record.artifact_id,
                            "extractor_model_id": record.extractor_model_id,
                            "confidence": relation.confidence,
                            "snippet_hash": snip_hash,
                            "source_run_id": run_id,
                        },
                        source_run_id=run_id,
                    )
                    if ee_created:
                        created_rels += 1
                    else:
                        updated_rels += 1

                    if rel_type in {"TAGGED_IN", "MENTIONS"}:
                        sp_created = self._graph_store.upsert_relationship(
                            rel_id=self._rel_id(
                                rel_type,
                                subject_id,
                                post_node_id,
                                record.artifact_id,
                                str(ridx),
                                "post",
                            ),
                            rel_type=rel_type,
                            from_node_id=subject_id,
                            to_node_id=post_node_id,
                            properties={
                                "artifact_id": record.artifact_id,
                                "extractor_model_id": record.extractor_model_id,
                                "confidence": relation.confidence,
                                "snippet_hash": snip_hash,
                                "source_run_id": run_id,
                            },
                            source_run_id=run_id,
                        )
                        if sp_created:
                            created_rels += 1
                        else:
                            updated_rels += 1

            status = "completed"
            error_message = None
        except Exception as exc:
            status = "failed"
            error_message = str(exc)
        finished_at = datetime.now(timezone.utc)
        return GraphInsertionRunResult(
            run_id=run_id,
            status=status,
            nodes_created=created_nodes,
            nodes_updated=updated_nodes,
            relationships_created=created_rels,
            relationships_updated=updated_rels,
            started_at=started_at,
            finished_at=finished_at,
            backend=self._graph_backend,
            error_message=error_message,
        )

    @staticmethod
    def _normalize_predicate(value: str) -> str:
        out = re.sub(r"[^A-Z_]+", "_", value.upper()).strip("_")
        if not out:
            return "MENTIONS"
        if out == "WORKS_AT":
            return "MENTIONS"
        return out

    @staticmethod
    def _rel_id(*parts: str) -> str:
        payload = "|".join(parts).encode("utf-8")
        return "rel_" + hashlib.sha1(payload).hexdigest()[:20]

    @staticmethod
    def _snippet_hash(text: str) -> str:
        return hashlib.sha1(text.encode("utf-8")).hexdigest()[:16]

    @staticmethod
    def _json_digest(obj: object) -> str:
        payload = json.dumps(obj, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
        return hashlib.sha256(payload).hexdigest()

    @staticmethod
    def _build_mention_map(records: list) -> dict[str, tuple[str, str]]:
        out: dict[str, tuple[str, str]] = {}
        for record in records:
            for idx, ent in enumerate(record.entities):
                out[f"{record.artifact_id}:e:{idx}"] = (ent.entity_type, ent.surface_form)
            for idx, rel in enumerate(record.relations):
                out[f"{record.artifact_id}:r:{idx}:s"] = ("UNKNOWN", rel.subject)
                out[f"{record.artifact_id}:r:{idx}:o"] = ("UNKNOWN", rel.object)
        return out

    @staticmethod
    def _infer_entity_kind(mention_ids: list[str], mention_map: dict[str, tuple[str, str]]) -> str:
        """Stored on `CanonicalEntity.entity_kind` (single graph label; kind is a property)."""
        entity_types = []
        for mention_id in mention_ids:
            entity_type, _ = mention_map.get(mention_id, ("UNKNOWN", ""))
            entity_types.append(entity_type.upper())
        if "PERSON" in entity_types:
            return "Person"
        if "ORG" in entity_types or "ORGANIZATION" in entity_types:
            return "Organization"
        if "LOCATION" in entity_types or "LOC" in entity_types:
            return "Location"
        return "Entity"
