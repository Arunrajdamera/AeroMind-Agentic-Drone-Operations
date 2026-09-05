from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import Field, field_validator

from aeromind.models.domain import MemoryScope, MemorySourceType, MemoryStatus, MemoryType
from aeromind.schemas.common import DomainModel


class MemoryCreate(DomainModel):
    memory_type: MemoryType
    scope: MemoryScope
    content: str = Field(min_length=1, max_length=10_000)
    structured_data: dict[str, Any] = Field(default_factory=dict)
    source: str = Field(min_length=1, max_length=128)
    source_type: MemorySourceType
    source_id: str = Field(min_length=1, max_length=128)
    confidence: float = Field(ge=0, le=1)
    importance: float = Field(ge=0, le=1)
    mission_id: UUID | None = None
    agent_run_id: UUID | None = None
    drone_id: UUID | None = None
    expires_at: datetime | None = None

    @field_validator("content")
    @classmethod
    def content_is_not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("content must not be blank")
        return value


class MemorySearch(DomainModel):
    query: str = Field(min_length=1, max_length=10_000)
    top_k: int = Field(default=5, ge=1, le=25)
    mission_id: UUID | None = None
    agent_run_id: UUID | None = None
    drone_id: UUID | None = None
    memory_type: MemoryType | None = None
    min_confidence: float = Field(default=0, ge=0, le=1)
    similarity_threshold: float = Field(default=0.15, ge=-1, le=1)
    active_only: bool = True


class MemoryEvidence(DomainModel):
    memory_id: UUID
    memory_type: MemoryType
    scope: MemoryScope
    content: str
    similarity_score: float
    confidence: float
    importance: float
    source: str
    source_type: MemorySourceType
    source_id: str
    structured_data: dict[str, Any] = Field(default_factory=dict)


class MemoryRead(MemoryEvidence):
    status: MemoryStatus
    mission_id: UUID | None = None
    agent_run_id: UUID | None = None
    drone_id: UUID | None = None
    expires_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class MemorySearchResult(DomainModel):
    memories: list[MemoryEvidence] = Field(default_factory=list)
