"""Deterministic heuristic extraction used for CI/offline runs."""

from __future__ import annotations

import re

from schemas.extraction_record import ExtractedEntity, ExtractedRelation
from schemas.raw_artifact import RawArtifact

_HASHTAG_RE = re.compile(r"#([A-Za-z0-9_]+)")
_MENTION_RE = re.compile(r"@([A-Za-z0-9._]+)")


class HeuristicExtractor:
    """Extract entities/relations from captions with simple rules."""

    def extract(self, artifact: RawArtifact) -> tuple[list[ExtractedEntity], list[ExtractedRelation]]:
        caption = artifact.caption_text or ""
        entities: list[ExtractedEntity] = []
        relations: list[ExtractedRelation] = []

        mentions = artifact.mentions or _MENTION_RE.findall(caption)
        hashtags = artifact.hashtags or _HASHTAG_RE.findall(caption)

        for m in mentions:
            entities.append(
                ExtractedEntity(
                    entity_type="Person",
                    surface_form=m,
                    snippet=f"@{m}",
                    confidence=0.75,
                )
            )
            relations.append(
                ExtractedRelation(
                    subject=artifact.platform_post_id,
                    predicate="MENTIONS",
                    object=m,
                    evidence_span=caption[:240],
                    confidence=0.75,
                )
            )

        for h in hashtags:
            entities.append(
                ExtractedEntity(
                    entity_type="Topic",
                    surface_form=h,
                    snippet=f"#{h}",
                    confidence=0.7,
                )
            )
            relations.append(
                ExtractedRelation(
                    subject=artifact.platform_post_id,
                    predicate="TAGGED_IN",
                    object=h,
                    evidence_span=caption[:240],
                    confidence=0.7,
                )
            )

        unique_entities: dict[tuple[str, str], ExtractedEntity] = {}
        for ent in entities:
            unique_entities[(ent.entity_type, ent.surface_form.lower())] = ent
        return list(unique_entities.values()), relations
