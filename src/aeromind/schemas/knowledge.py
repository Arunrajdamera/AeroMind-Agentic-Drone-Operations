from __future__ import annotations

from typing import Any
from uuid import UUID

from pydantic import Field, field_validator

from aeromind.schemas.common import DomainModel


class DocumentIngestRequest(DomainModel):
    title: str = Field(min_length=1, max_length=256)
    content: str = Field(min_length=1, max_length=100_000)
    source: str = Field(min_length=1, max_length=512)
    metadata: dict[str, Any] = Field(default_factory=dict)
    external_reference: str | None = Field(default=None, max_length=512)

    @field_validator("content")
    @classmethod
    def content_must_not_be_whitespace(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("content must not be empty")
        return value


class DocumentIngestResult(DomainModel):
    document_id: UUID
    content_hash: str
    chunk_count: int
    created: bool


class RetrievedChunk(DomainModel):
    document_id: UUID
    chunk_id: UUID
    source: str
    similarity_score: float
    metadata: dict[str, Any] = Field(default_factory=dict)
    content_excerpt: str


class KnowledgeSearchRequest(DomainModel):
    query: str = Field(min_length=1, max_length=10_000)
    top_k: int = Field(default=5, ge=1, le=25)
    similarity_threshold: float | None = Field(default=None, ge=-1, le=1)


class KnowledgeSearchResult(DomainModel):
    answer: str
    confidence: float = Field(ge=0, le=1)
    sources: list[str] = Field(default_factory=list)
    retrieved_chunks: list[RetrievedChunk] = Field(default_factory=list)
