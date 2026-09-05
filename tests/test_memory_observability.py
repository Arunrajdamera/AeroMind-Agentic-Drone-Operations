from __future__ import annotations

import logging
from uuid import uuid4

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from aeromind.core.exceptions import DomainError
from aeromind.core.logging import JsonFormatter
from aeromind.models.domain import Approval, MemoryScope, MemorySourceType, MemoryType
from aeromind.providers.interfaces import EmbeddingProvider
from aeromind.schemas.memory import MemoryCreate, MemorySearch
from aeromind.services.memory import MemoryService
from aeromind.tools.definitions import ToolExecutionResult, ToolStatus


def session() -> Session:
    from aeromind.db.base import Base

    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    return Session(engine)


def data(**overrides: object) -> MemoryCreate:
    values: dict[str, object] = {
        "memory_type": MemoryType.SYSTEM_OBSERVATION,
        "scope": MemoryScope.RUN,
        "content": "SENSITIVE-MEMORY-CONTENT-DO-NOT-LOG",
        "source": "test",
        "source_type": MemorySourceType.SYSTEM_OBSERVATION,
        "source_id": "observation-1",
        "confidence": 0.8,
        "importance": 0.5,
    }
    values.update(overrides)
    return MemoryCreate(**values)


class FailingEmbeddingProvider(EmbeddingProvider):
    async def embed(self, texts: list[str]) -> list[list[float]]:
        del texts
        raise DomainError("SENSITIVE-API-KEY-MUST-NOT-LOG")


def events(caplog: pytest.LogCaptureFixture, operation: str) -> list[logging.LogRecord]:
    return [record for record in caplog.records if getattr(record, "operation", None) == operation]


def test_memory_creation_and_embedding_emit_safe_timing_telemetry(
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.INFO, logger="aeromind.services.memory")
    MemoryService(session()).create_memory(data())
    create, embedding = events(caplog, "memory.create"), events(caplog, "embedding.generate")
    assert create[-1].success and create[-1].memory_created and create[-1].latency_ms >= 0
    assert embedding[-1].success and embedding[-1].provider == "MockEmbeddingProvider"
    rendered = "\n".join(JsonFormatter().format(record) for record in caplog.records)
    assert "SENSITIVE-MEMORY-CONTENT-DO-NOT-LOG" not in rendered
    assert "[" not in rendered  # embedding vectors are not serialized into telemetry


def test_memory_retrieval_emits_result_count_and_safe_failure_telemetry(
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.INFO, logger="aeromind.services.memory")
    service = MemoryService(session())
    service.create_memory(data(content="retrieval telemetry test"))
    service.retrieve_memories(
        MemorySearch(query="retrieval telemetry test", similarity_threshold=0)
    )
    retrieved = events(caplog, "memory.retrieve")[-1]
    assert retrieved.success and retrieved.result_count == 1 and retrieved.latency_ms >= 0

    failed = MemoryService(session(), provider=FailingEmbeddingProvider())
    with pytest.raises(DomainError):
        failed.retrieve_memories(MemorySearch(query="failure"))
    embedding_failure = events(caplog, "embedding.generate")[-1]
    retrieval_failure = events(caplog, "memory.retrieve")[-1]
    assert (
        not embedding_failure.success and embedding_failure.error_type == "embedding_provider_error"
    )
    assert (
        not retrieval_failure.success and retrieval_failure.error_type == "memory_retrieval_error"
    )
    rendered = "\n".join(JsonFormatter().format(record) for record in caplog.records)
    assert "SENSITIVE-API-KEY-MUST-NOT-LOG" not in rendered


def test_memory_creation_and_approval_outcome_failures_emit_safe_telemetry(
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.INFO, logger="aeromind.services.memory")
    service = MemoryService(session())
    with pytest.raises(DomainError):
        service.create_memory(
            data(scope=MemoryScope.GLOBAL, source_type=MemorySourceType.AGENT_RUN)
        )
    failed_create = events(caplog, "memory.create")[-1]
    assert not failed_create.success and failed_create.error_type == "memory_write_error"

    approval = Approval(
        status="APPROVED",
        tool_name="return_to_home",
        payload={"call": {"drone_id": "DR-OBS"}, "run_id": None},
    )
    service.session.add(approval)
    service.session.flush()
    service.record_approval_outcome(
        approval,
        ToolExecutionResult(
            execution_id=str(uuid4()),
            tool_name="return_to_home",
            status=ToolStatus.SUCCEEDED,
        ),
    )
    outcome = events(caplog, "memory.approval_outcome")[-1]
    assert outcome.success and outcome.outcome_category == "SUCCEEDED"


def test_approval_outcome_recording_failure_emits_safe_telemetry(
    caplog: pytest.LogCaptureFixture, monkeypatch: pytest.MonkeyPatch
) -> None:
    caplog.set_level(logging.INFO, logger="aeromind.services.memory")
    service = MemoryService(session())
    approval = Approval(
        status="REJECTED",
        tool_name="return_to_home",
        payload={"call": {"drone_id": "DR-OBS"}, "run_id": None},
    )
    service.session.add(approval)
    service.session.flush()

    def fail_create(*_args: object, **_kwargs: object) -> object:
        raise DomainError("SENSITIVE-MEMORY-WRITE-DETAIL-MUST-NOT-LOG")

    monkeypatch.setattr(service, "create_memory", fail_create)
    with pytest.raises(DomainError):
        service.record_approval_outcome(approval)

    failed = events(caplog, "memory.approval_outcome")[-1]
    assert not failed.success and failed.error_type == "memory_recording_error"
    rendered = "\n".join(JsonFormatter().format(record) for record in caplog.records)
    assert "SENSITIVE-MEMORY-WRITE-DETAIL-MUST-NOT-LOG" not in rendered
