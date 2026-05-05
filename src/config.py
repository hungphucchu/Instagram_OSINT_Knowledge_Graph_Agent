"""Application settings loaded from environment (see `.env.example`)."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Single configuration surface for Phase 0; extended in later phases."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        # Allow `Settings(collection_db_path=...)` in tests; aliases still map env vars.
        populate_by_name=True,
    )

    data_dir: Path = Field(default=Path("data"), validation_alias="DATA_DIR")
    apify_cache_dir: Path = Field(default=Path("apify_cache"), validation_alias="APIFY_CACHE_DIR")
    collection_mode: Literal["fixture", "apify_data", "apify"] = Field(
        default="fixture",
        validation_alias="COLLECTION_MODE",
    )
    collection_fixture_path: Path = Field(
        default=Path("fixtures/raw_artifacts.json"),
        validation_alias="COLLECTION_FIXTURE_PATH",
    )
    collection_db_path: Path = Field(
        default=Path("data/raw_artifacts.db"),
        validation_alias="COLLECTION_DB_PATH",
    )
    apify_data_path: Path = Field(
        default=Path("apify_data/dataset.json"),
        validation_alias="APIFY_DATA_PATH",
    )
    apify_api_token: str = Field(default="", validation_alias="APIFY_API_TOKEN")
    apify_actor_id: str = Field(default="", validation_alias="APIFY_ACTOR_ID")
    apify_max_items_per_run: int = Field(
        default=50,
        validation_alias="APIFY_MAX_ITEMS_PER_RUN",
        description="0 = no cap on rows returned (apify_data/fixture reads full file; live Apify requests up to 50k).",
    )
    apify_run_timeout_seconds: int = Field(default=300, validation_alias="APIFY_RUN_TIMEOUT_SECONDS")
    apify_poll_interval_seconds: int = Field(default=5, validation_alias="APIFY_POLL_INTERVAL_SECONDS")
    extract_mode: Literal["heuristic", "llm"] = Field(default="heuristic", validation_alias="EXTRACT_MODE")
    extract_llm_provider: str = Field(default="openai", validation_alias="EXTRACT_LLM_PROVIDER")
    extract_llm_model: str = Field(default="gpt-4o-mini", validation_alias="EXTRACT_LLM_MODEL")
    extract_llm_base_url: str = Field(
        default="https://api.openai.com/v1",
        validation_alias="EXTRACT_LLM_BASE_URL",
    )
    extract_llm_api_key: str = Field(default="", validation_alias="EXTRACT_LLM_API_KEY")
    extract_llm_timeout_seconds: int = Field(
        default=90,
        validation_alias="EXTRACT_LLM_TIMEOUT_SECONDS",
    )
    extract_max_concurrency: int = Field(default=4, validation_alias="EXTRACT_MAX_CONCURRENCY")
    extraction_db_path: Path = Field(
        default=Path("data/extraction_records.db"),
        validation_alias="EXTRACTION_DB_PATH",
    )
    dedup_db_path: Path = Field(
        default=Path("data/dedup_reports.db"),
        validation_alias="DEDUP_DB_PATH",
    )
    dedup_embedding_backend: Literal["char_ngram", "off"] = Field(
        default="char_ngram",
        validation_alias="DEDUP_EMBEDDING_BACKEND",
    )
    dedup_fuzzy_merge_threshold: float = Field(default=0.90, validation_alias="DEDUP_FUZZY_MERGE_THRESHOLD")
    dedup_embedding_merge_threshold: float = Field(
        default=0.82,
        validation_alias="DEDUP_EMBEDDING_MERGE_THRESHOLD",
    )
    dedup_fuzzy_review_threshold: float = Field(
        default=0.78,
        validation_alias="DEDUP_FUZZY_REVIEW_THRESHOLD",
    )
    dedup_char_ngram_n: int = Field(default=3, validation_alias="DEDUP_CHAR_NGRAM_N")
    graph_backend: Literal["neo4j"] = Field(
        default="neo4j",
        validation_alias="GRAPH_BACKEND",
    )
    neo4j_uri: str = Field(default="", validation_alias="NEO4J_URI")
    neo4j_user: str = Field(default="", validation_alias="NEO4J_USER")
    neo4j_password: str = Field(default="", validation_alias="NEO4J_PASSWORD")
    neo4j_database: str = Field(default="neo4j", validation_alias="NEO4J_DATABASE")
    quality_report_dir: Path = Field(default=Path("reports"), validation_alias="QUALITY_REPORT_DIR")
    quality_max_attempts: int = Field(
        default=2,
        ge=1,
        validation_alias="QUALITY_MAX_ATTEMPTS",
        description="How many quality gate evaluations per pipeline run (initial + retries).",
    )
    quality_retry_target: Literal["extract", "dedup"] = Field(
        default="extract",
        validation_alias="QUALITY_RETRY_TARGET",
    )
    quality_fail_on_warning: bool = Field(default=False, validation_alias="QUALITY_FAIL_ON_WARNING")
    quality_llm_enabled: bool = Field(default=False, validation_alias="QUALITY_LLM_ENABLED")
    quality_llm_provider: str = Field(default="openai", validation_alias="QUALITY_LLM_PROVIDER")
    quality_llm_model: str = Field(default="gpt-4o-mini", validation_alias="QUALITY_LLM_MODEL")
    quality_llm_base_url: str = Field(
        default="https://api.openai.com/v1",
        validation_alias="QUALITY_LLM_BASE_URL",
    )
    quality_llm_api_key: str = Field(default="", validation_alias="QUALITY_LLM_API_KEY")
    quality_llm_timeout_seconds: int = Field(default=60, validation_alias="QUALITY_LLM_TIMEOUT_SECONDS")
    quality_llm_sample_size: int = Field(default=10, ge=0, validation_alias="QUALITY_LLM_SAMPLE_SIZE")
    quality_llm_max_concurrency: int = Field(default=4, ge=1, validation_alias="QUALITY_LLM_MAX_CONCURRENCY")
    quality_llm_min_score_threshold: float = Field(
        default=0.75,
        ge=0.0,
        le=1.0,
        validation_alias="QUALITY_LLM_MIN_SCORE_THRESHOLD",
    )
    query_llm_enabled: bool = Field(default=False, validation_alias="QUERY_LLM_ENABLED")
    query_llm_provider: str = Field(default="openai", validation_alias="QUERY_LLM_PROVIDER")
    query_llm_model: str = Field(default="gpt-4o-mini", validation_alias="QUERY_LLM_MODEL")
    query_llm_base_url: str = Field(default="https://api.openai.com/v1", validation_alias="QUERY_LLM_BASE_URL")
    query_llm_api_key: str = Field(default="", validation_alias="QUERY_LLM_API_KEY")
    query_llm_timeout_seconds: int = Field(default=60, validation_alias="QUERY_LLM_TIMEOUT_SECONDS")
    query_max_limit: int = Field(default=50, ge=1, le=2000, validation_alias="QUERY_MAX_LIMIT")
    query_max_evidence_rows: int = Field(default=20, ge=1, le=200, validation_alias="QUERY_MAX_EVIDENCE_ROWS")
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = Field(
        default="INFO",
        validation_alias="LOG_LEVEL",
    )

    @field_validator("data_dir", mode="before")
    @classmethod
    def _coerce_data_dir(cls, v: object) -> Path:
        if v is None or v == "":
            return Path("data")
        return Path(v)

    @field_validator("apify_cache_dir", mode="before")
    @classmethod
    def _coerce_apify_cache_dir(cls, v: object) -> Path:
        if v is None or v == "":
            return Path("apify_cache")
        return Path(v)

    @field_validator(
        "collection_fixture_path",
        "collection_db_path",
        "apify_data_path",
        "extraction_db_path",
        "dedup_db_path",
        "quality_report_dir",
        mode="before",
    )
    @classmethod
    def _coerce_collection_paths(cls, v: object, info: object) -> Path:
        if v is None or v == "":
            if getattr(info, "field_name", "") == "collection_db_path":
                return Path("data/raw_artifacts.db")
            if getattr(info, "field_name", "") == "extraction_db_path":
                return Path("data/extraction_records.db")
            if getattr(info, "field_name", "") == "dedup_db_path":
                return Path("data/dedup_reports.db")
            if getattr(info, "field_name", "") == "quality_report_dir":
                return Path("reports")
            if getattr(info, "field_name", "") == "apify_data_path":
                return Path("apify_data/dataset.json")
            return Path("fixtures/raw_artifacts.json")
        return Path(v)


@lru_cache
def get_settings() -> Settings:
    return Settings()
