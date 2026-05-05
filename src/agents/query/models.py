"""Phase 6 data contracts for query answering."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class QueryRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    question: str
    include_cypher: bool = True


class QueryResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    answer: str
    evidence: list[dict] = Field(default_factory=list)
    cypher: str | None = None
    query_id: str
    warnings: list[str] = Field(default_factory=list)

