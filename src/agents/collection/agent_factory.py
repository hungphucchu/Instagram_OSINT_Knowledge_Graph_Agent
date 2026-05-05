"""Construct CollectionAgent from application settings (CLI + LangGraph)."""

from __future__ import annotations

from agents.collection.apify_cache_store import ApifyCacheStore
from agents.collection.apify_client import ApifyClient
from agents.collection.apify_data_source_adapter import ApifyDataSourceAdapter
from agents.collection.apify_source_adapter import ApifySourceAdapter
from agents.collection.collection_agent import CollectionAgent
from agents.collection.fixture_source_adapter import FixtureSourceAdapter
from agents.collection.raw_artifact_store import RawArtifactStore
from config import Settings


def build_collection_agent(
    settings: Settings,
    *,
    store: RawArtifactStore | None = None,
) -> CollectionAgent:
    raw_store = store or RawArtifactStore(db_path=settings.collection_db_path)

    if settings.collection_mode == "fixture":
        adapter = FixtureSourceAdapter(fixture_path=settings.collection_fixture_path)
        return CollectionAgent(adapter=adapter, store=raw_store)

    if settings.collection_mode == "apify_data":
        adapter = ApifyDataSourceAdapter(dataset_path=settings.apify_data_path)
        return CollectionAgent(adapter=adapter, store=raw_store)

    if not settings.apify_api_token or not settings.apify_actor_id:
        raise ValueError("APIFY_API_TOKEN and APIFY_ACTOR_ID are required for COLLECTION_MODE=apify")

    cache = ApifyCacheStore(cache_dir=settings.apify_cache_dir)
    client = ApifyClient(api_token=settings.apify_api_token, cache_store=cache)
    adapter = ApifySourceAdapter(
        client=client,
        actor_id=settings.apify_actor_id,
        run_timeout_seconds=settings.apify_run_timeout_seconds,
        poll_interval_seconds=settings.apify_poll_interval_seconds,
    )
    return CollectionAgent(adapter=adapter, store=raw_store)
