from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import math
from collections.abc import Sequence
from datetime import UTC, datetime
from time import perf_counter
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from aeromind.core.config import Settings, get_settings
from aeromind.core.exceptions import DomainError
from aeromind.models.domain import (
    AgentRun,
    Approval,
    Drone,
    MemoryRecord,
    MemoryScope,
    MemorySourceType,
    MemoryStatus,
    MemoryType,
    Mission,
)
from aeromind.providers.interfaces import EmbeddingProvider
from aeromind.providers.mock import MockEmbeddingProvider
from aeromind.schemas.memory import (
    MemoryCreate,
    MemoryEvidence,
    MemoryRead,
    MemorySearch,
    MemorySearchResult,
)
from aeromind.tools.definitions import ToolExecutionResult

logger = logging.getLogger(__name__)


def _cosine_similarity(left: Sequence[float], right: Sequence[float]) -> float:
    dot = sum(a * b for a, b in zip(left, right, strict=True))
    left_norm = math.sqrt(sum(a * a for a in left))
    right_norm = math.sqrt(sum(b * b for b in right))
    return dot / (left_norm * right_norm) if left_norm and right_norm else 0.0


class MemoryService:
    """Controlled, provenance-backed operational memory; never an authorization channel."""

    def __init__(
        self,
        session: Session,
        provider: EmbeddingProvider | None = None,
        settings: Settings | None = None,
    ) -> None:
        self.session = session
        self.provider = provider or MockEmbeddingProvider()
        self.settings = settings or get_settings()

    def create_memory(self, data: MemoryCreate) -> tuple[MemoryRecord, bool]:
        started = perf_counter()
        try:
            self._validate_scope(data)
            content = " ".join(data.content.split())
            if not content:
                raise DomainError("Memory content must not be empty")
            content_hash = self._content_hash(data, content)
            existing = self.session.scalar(
                select(MemoryRecord).where(MemoryRecord.content_hash == content_hash)
            )
            if existing:
                self._log(
                    "memory.create",
                    started,
                    memory_type=data.memory_type.value,
                    scope=data.scope.value,
                    memory_created=False,
                )
                return existing, False
            embedding = self._embed([content])[0]
            record = MemoryRecord(
                memory_type=data.memory_type,
                scope=data.scope,
                content=content,
                structured_data=data.structured_data,
                source=data.source,
                source_type=data.source_type,
                source_id=data.source_id,
                confidence=data.confidence,
                importance=data.importance,
                mission_id=data.mission_id,
                agent_run_id=data.agent_run_id,
                drone_id=data.drone_id,
                expires_at=data.expires_at,
                content_hash=content_hash,
                embedding=embedding,
                embedding_model=self.settings.embedding_model_name,
            )
            self.session.add(record)
            self.session.flush()
        except Exception:
            self.session.rollback()
            self._log(
                "memory.create",
                started,
                success=False,
                memory_type=data.memory_type.value,
                scope=data.scope.value,
                error_type="memory_write_error",
            )
            raise
        self._log(
            "memory.create",
            started,
            memory_type=data.memory_type.value,
            scope=data.scope.value,
            memory_created=True,
        )
        return record, True

    def get_memory(self, memory_id: UUID) -> MemoryRecord | None:
        record = self.session.get(MemoryRecord, memory_id)
        if record:
            self._expire_if_due(record)
        return record

    def update_memory_status(self, memory_id: UUID, status: MemoryStatus) -> MemoryRecord:
        record = self.get_memory(memory_id)
        if not record:
            raise DomainError("Memory was not found")
        if record.status != MemoryStatus.ACTIVE:
            raise DomainError("Only active memory can change lifecycle status")
        if status not in {MemoryStatus.ARCHIVED, MemoryStatus.INVALIDATED}:
            raise DomainError("Invalid memory lifecycle transition")
        record.status = status
        self.session.flush()
        return record

    def retrieve_memories(self, request: MemorySearch) -> MemorySearchResult:
        started = perf_counter()
        try:
            query = " ".join(request.query.split())
            if not query:
                raise DomainError("Memory query must not be empty")
            self._expire_due_memories()
            query_embedding = self._embed([query])[0]
            records = self._filtered_records(request)
            scored = self._search(records, query_embedding, request.similarity_threshold)
            result = MemorySearchResult(
                memories=[
                    self._evidence(record, score) for record, score in scored[: request.top_k]
                ]
            )
        except Exception:
            self._log(
                "memory.retrieve", started, success=False, error_type="memory_retrieval_error"
            )
            raise
        self._log("memory.retrieve", started, result_count=len(result.memories))
        return result

    def record_run_outcomes(self, state: dict[str, Any]) -> list[MemoryRecord]:
        """Persist only concise reusable outcomes, never prompts or hidden reasoning."""
        run = self.session.scalar(select(AgentRun).where(AgentRun.run_id == state["run_id"]))
        if not run or not state.get("decision"):
            return []
        event = state["incoming_event"]
        mission = state.get("mission_context")
        drone = state.get("drone_context")
        decision = state["decision"]
        common = {
            "mission_id": mission.id if mission else None,
            "agent_run_id": run.id,
            "drone_id": drone.id if drone else None,
            "source": "agent_orchestrator",
            "source_type": MemorySourceType.AGENT_RUN,
            "source_id": state["run_id"],
            "confidence": decision.confidence,
            "importance": 0.9 if decision.requires_approval else 0.6,
        }
        structured = {
            "event_id": event.event_id,
            "event_type": event.event_type.value,
            "severity": event.severity.value,
            "decision": decision.decision.value,
            "approval_required": decision.requires_approval,
            "execution_status": state.get("execution_status"),
        }
        records: list[MemoryRecord] = []
        item, created = self.create_memory(
            MemoryCreate(
                memory_type=MemoryType.DECISION_OUTCOME,
                scope=MemoryScope.MISSION if mission else MemoryScope.RUN,
                content=(
                    f"Event {event.event_id} was assessed as {decision.decision.value}; "
                    f"approval required: {decision.requires_approval}."
                ),
                structured_data=structured,
                **common,
            )
        )
        if created:
            records.append(item)
        for result in state.get("tool_results", []):
            status = getattr(result, "status", None)
            name = getattr(result, "tool_name", None)
            if not status or not name:
                continue
            tool_data = {**structured, "tool": name, "tool_status": status.value}
            item, created = self.create_memory(
                MemoryCreate(
                    memory_type=MemoryType.TOOL_OUTCOME,
                    scope=MemoryScope.MISSION if mission else MemoryScope.RUN,
                    content=f"Simulated tool {name} completed with status {status.value}.",
                    structured_data=tool_data,
                    importance=0.8 if status.value == "REQUIRES_APPROVAL" else 0.5,
                    **{key: value for key, value in common.items() if key != "importance"},
                )
            )
            if created:
                records.append(item)
        return records

    def record_approval_outcome(
        self, approval: Approval, execution: ToolExecutionResult | None = None
    ) -> tuple[MemoryRecord, bool]:
        """Record a terminal approval outcome after authorization has completed."""
        started = perf_counter()
        try:
            call = approval.payload.get("call")
            call = call if isinstance(call, dict) else {}
            public_run_id = approval.payload.get("run_id")
            run = (
                self.session.scalar(select(AgentRun).where(AgentRun.run_id == public_run_id))
                if isinstance(public_run_id, str)
                else None
            )
            mission = (
                self.session.scalar(
                    select(Mission).where(Mission.mission_id == call.get("mission_id"))
                )
                if isinstance(call.get("mission_id"), str)
                else None
            )
            drone = (
                self.session.scalar(select(Drone).where(Drone.drone_id == call.get("drone_id")))
                if isinstance(call.get("drone_id"), str)
                else None
            )
            execution_status = execution.status.value if execution else approval.status
            content = (
                f"Approval {approval.id} for simulated tool {approval.tool_name or 'unknown'} "
                f"ended as {execution_status}."
            )
            result = self.create_memory(
                MemoryCreate(
                    memory_type=MemoryType.TOOL_OUTCOME,
                    scope=MemoryScope.MISSION if mission else MemoryScope.RUN,
                    content=content,
                    structured_data={
                        "approval_id": str(approval.id),
                        "approval_status": approval.status,
                        "tool": approval.tool_name,
                        "execution_status": execution_status,
                        "execution_error": execution.error if execution else None,
                    },
                    source="approval_service",
                    source_type=MemorySourceType.APPROVAL,
                    source_id=str(approval.id),
                    confidence=1.0,
                    importance=0.9,
                    mission_id=mission.id if mission else approval.mission_id,
                    agent_run_id=run.id if run else None,
                    drone_id=drone.id if drone else None,
                )
            )
        except Exception:
            self._log(
                "memory.approval_outcome",
                started,
                success=False,
                error_type="memory_recording_error",
            )
            raise
        self._log("memory.approval_outcome", started, outcome_category=execution_status)
        return result

    def _embed(self, texts: list[str]) -> list[list[float]]:
        started = perf_counter()
        provider = type(self.provider).__name__
        model_name = getattr(self.provider, "model_name", self.settings.embedding_model_name)
        try:
            vectors = asyncio.run(self.provider.embed(texts))
            if len(vectors) != len(texts):
                raise DomainError("Embedding provider returned an unexpected embedding count")
            if any(len(vector) != self.settings.embedding_dimensions for vector in vectors):
                raise DomainError("Embedding provider returned an unexpected embedding dimension")
        except Exception:
            self._log(
                "embedding.generate",
                started,
                success=False,
                provider=provider,
                model_name=model_name,
                error_type="embedding_provider_error",
            )
            raise
        self._log("embedding.generate", started, provider=provider, model_name=model_name)
        return vectors

    def _log(self, operation: str, started: float, success: bool = True, **safe: object) -> None:
        logger.info(
            operation,
            extra={
                "operation": operation,
                "success": success,
                "latency_ms": round((perf_counter() - started) * 1000, 3),
                **safe,
            },
        )

    def _filtered_records(self, request: MemorySearch) -> list[MemoryRecord]:
        query = select(MemoryRecord).where(MemoryRecord.confidence >= request.min_confidence)
        if request.active_only:
            query = query.where(MemoryRecord.status == MemoryStatus.ACTIVE)
        if request.mission_id:
            query = query.where(MemoryRecord.mission_id == request.mission_id)
        if request.agent_run_id:
            query = query.where(MemoryRecord.agent_run_id == request.agent_run_id)
        if request.drone_id:
            query = query.where(MemoryRecord.drone_id == request.drone_id)
        if request.memory_type:
            query = query.where(MemoryRecord.memory_type == request.memory_type)
        return list(self.session.scalars(query))

    def _search(
        self, records: list[MemoryRecord], embedding: list[float], threshold: float
    ) -> list[tuple[MemoryRecord, float]]:
        if self.session.bind is not None and self.session.bind.dialect.name == "postgresql":
            distance = MemoryRecord.embedding.cosine_distance(embedding)
            rows = self.session.execute(
                select(MemoryRecord, distance.label("distance"))
                .where(MemoryRecord.id.in_([record.id for record in records]))
                .order_by(distance)
            ).all()
            return [
                (record, 1.0 - float(distance))
                for record, distance in rows
                if 1.0 - float(distance) >= threshold
            ]
        values = [
            (record, _cosine_similarity(embedding, record.embedding))
            for record in records
            if record.embedding is not None
        ]
        return sorted(
            (value for value in values if value[1] >= threshold),
            key=lambda value: value[1],
            reverse=True,
        )

    def _expire_due_memories(self) -> None:
        for record in self.session.scalars(
            select(MemoryRecord).where(MemoryRecord.status == MemoryStatus.ACTIVE)
        ):
            self._expire_if_due(record)
        self.session.flush()

    def _expire_if_due(self, record: MemoryRecord) -> None:
        expires_at = record.expires_at
        if expires_at and expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=UTC)
        if record.status == MemoryStatus.ACTIVE and expires_at and expires_at <= datetime.now(UTC):
            record.status = MemoryStatus.EXPIRED

    def _content_hash(self, data: MemoryCreate, content: str) -> str:
        material = json.dumps(
            {
                "content": content,
                "type": data.memory_type.value,
                "scope": data.scope.value,
                "source": data.source,
                "source_type": data.source_type.value,
                "source_id": data.source_id,
                "structured_data": data.structured_data,
            },
            sort_keys=True,
            default=str,
        )
        return hashlib.sha256(material.encode("utf-8")).hexdigest()

    def _validate_scope(self, data: MemoryCreate) -> None:
        if data.scope == MemoryScope.GLOBAL and data.source_type == MemorySourceType.AGENT_RUN:
            raise DomainError("Agent run output cannot create global memory")

    def _evidence(self, record: MemoryRecord, score: float) -> MemoryEvidence:
        return MemoryEvidence(
            memory_id=record.id,
            memory_type=record.memory_type,
            scope=record.scope,
            content=record.content,
            similarity_score=round(score, 6),
            confidence=record.confidence,
            importance=record.importance,
            source=record.source,
            source_type=record.source_type,
            source_id=record.source_id,
            structured_data=record.structured_data,
        )

    def as_read(self, record: MemoryRecord) -> MemoryRead:
        return MemoryRead(
            **self._evidence(record, 1.0).model_dump(),
            status=record.status,
            mission_id=record.mission_id,
            agent_run_id=record.agent_run_id,
            drone_id=record.drone_id,
            expires_at=record.expires_at,
            created_at=record.created_at,
            updated_at=record.updated_at,
        )
