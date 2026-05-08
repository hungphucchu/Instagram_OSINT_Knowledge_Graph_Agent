"""Wiring Settings + stores + agents for the linear ingest graph."""

from __future__ import annotations

from dataclasses import dataclass

from config import Settings

from agents.collection import CollectionAgent, RawArtifactStore
from agents.collection.agent_factory import build_collection_agent
from agents.deduplication import DedupAgent, DedupStore
from agents.extraction import ExtractionAgent, ExtractionStore
from agents.graph_insertion import GraphInsertionAgent
from agents.quality.quality_agent import QualityAgent


@dataclass(frozen=True)
class PipelineRuntime:
    """Dependencies shared by all LangGraph nodes (same paths the CLI uses)."""

    settings: Settings
    raw_store: RawArtifactStore
    extraction_store: ExtractionStore
    dedup_store: DedupStore
    collection_agent: CollectionAgent
    graph_store: object

    @staticmethod
    def from_settings(
        settings: Settings,
        *,
        graph_store: object | None = None,
    ) -> PipelineRuntime:
        raw_store = RawArtifactStore(db_path=settings.collection_db_path)
        extraction_store = ExtractionStore(db_path=settings.extraction_db_path)
        dedup_store = DedupStore(db_path=settings.dedup_db_path)

        if graph_store is None:
            from agents.graph_insertion import Neo4jGraphStore

            graph_store = Neo4jGraphStore(
                uri=settings.neo4j_uri,
                user=settings.neo4j_user,
                password=settings.neo4j_password,
                database=settings.neo4j_database,
            )

        collection_agent = build_collection_agent(settings, store=raw_store)
        return PipelineRuntime(
            settings=settings,
            raw_store=raw_store,
            extraction_store=extraction_store,
            dedup_store=dedup_store,
            collection_agent=collection_agent,
            graph_store=graph_store,
        )

    def extraction_agent(self) -> ExtractionAgent:
        s = self.settings
        return ExtractionAgent(
            raw_store=self.raw_store,
            extraction_store=self.extraction_store,
            mode=s.extract_mode,
            llm_provider=s.extract_llm_provider,
            llm_model=s.extract_llm_model,
            llm_base_url=s.extract_llm_base_url,
            llm_api_key=s.extract_llm_api_key,
            llm_timeout_seconds=s.extract_llm_timeout_seconds,
            max_concurrency=s.extract_max_concurrency,
        )

    def dedup_agent(self) -> DedupAgent:
        s = self.settings
        return DedupAgent(
            extraction_store=self.extraction_store,
            dedup_store=self.dedup_store,
            embedding_backend=s.dedup_embedding_backend,
            fuzzy_merge_threshold=s.dedup_fuzzy_merge_threshold,
            embedding_merge_threshold=s.dedup_embedding_merge_threshold,
            fuzzy_review_threshold=s.dedup_fuzzy_review_threshold,
            char_ngram_n=s.dedup_char_ngram_n,
        )

    def graph_insertion_agent(self) -> GraphInsertionAgent:
        s = self.settings
        return GraphInsertionAgent(
            graph_backend=s.graph_backend,
            graph_store=self.graph_store,
            raw_store=self.raw_store,
            extraction_store=self.extraction_store,
            dedup_store=self.dedup_store,
        )

    def quality_agent(self) -> QualityAgent:
        return QualityAgent(
            settings=self.settings,
            graph_store=self.graph_store,
            raw_store=self.raw_store,
            extraction_store=self.extraction_store,
        )
