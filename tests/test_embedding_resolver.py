from __future__ import annotations

import asyncio
from uuid import uuid4

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

import aeromind.graph.workflow as workflow_module
from aeromind.core.config import Settings
from aeromind.core.exceptions import DomainError, ProviderConfigurationError
from aeromind.db.base import Base
from aeromind.models.domain import (
    Drone,
    DroneStatus,
    Event,
    EventType,
    HealthStatus,
    Mission,
    MissionStatus,
    MissionType,
    Priority,
)
from aeromind.providers.embedding import OpenAICompatibleEmbeddingProvider
from aeromind.providers.interfaces import EmbeddingProvider
from aeromind.providers.mock import MockEmbeddingProvider
from aeromind.providers.resolver import resolve_embedding_provider
from aeromind.schemas.memory import MemoryCreate
from aeromind.services.memory import MemoryService


class CountingEmbeddingProvider(EmbeddingProvider):
    def __init__(self, dimensions: int = 8) -> None:
        self.dimensions = dimensions
        self.calls: list[list[str]] = []

    async def embed(self, texts: list[str]) -> list[list[float]]:
        self.calls.append(texts)
        return [[float(index + 1) for index in range(self.dimensions)] for _ in texts]


def test_resolver_selects_deterministic_mock_provider() -> None:
    provider = resolve_embedding_provider(Settings(embedding_provider="mock"))
    assert isinstance(provider, MockEmbeddingProvider)
    assert asyncio.run(provider.embed(["same"])) == asyncio.run(provider.embed(["same"]))


def test_resolver_selects_openai_compatible_provider_without_network() -> None:
    provider = resolve_embedding_provider(
        Settings(
            embedding_provider="openai_compatible",
            embedding_model_name="controlled-test-embedding",
            embedding_api_key="not-a-real-key",
            embedding_base_url="https://embedding.example/v1",
        )
    )
    assert isinstance(provider, OpenAICompatibleEmbeddingProvider)
    assert provider.model_name == "controlled-test-embedding"
    assert provider.dimensions == 8


@pytest.mark.parametrize(
    "settings",
    [
        Settings(embedding_provider="openai_compatible", embedding_model_name="model"),
        Settings(
            embedding_provider="openai_compatible",
            embedding_model_name="model",
            embedding_api_key="key",
        ),
    ],
)
def test_configured_provider_missing_settings_fails_without_mock_fallback(
    settings: Settings,
) -> None:
    with pytest.raises(ProviderConfigurationError):
        resolve_embedding_provider(settings)


def test_configured_provider_response_dimension_is_rejected(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    provider = OpenAICompatibleEmbeddingProvider(
        base_url="https://embedding.example/v1",
        api_key="not-a-real-key",
        model_name="controlled-test-embedding",
        dimensions=8,
    )
    monkeypatch.setattr(provider, "_embed_sync", lambda texts: [[0.0] for _ in texts])
    with pytest.raises(DomainError, match="dimension"):
        asyncio.run(provider.embed(["dimension check"]))


def test_memory_service_preserves_explicit_provider_dependency_injection() -> None:
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    provider = CountingEmbeddingProvider()
    service = MemoryService(Session(engine), provider=provider)
    assert service.provider is provider
    service.create_memory(
        MemoryCreate(
            memory_type="SYSTEM_OBSERVATION",
            scope="RUN",
            content="Injected provider is used.",
            source="test",
            source_type="SYSTEM_OBSERVATION",
            source_id="provider-injection",
            confidence=0.8,
            importance=0.5,
        )
    )
    assert provider.calls == [["Injected provider is used."]]


def test_memory_service_rejects_wrong_dimension_from_injected_provider() -> None:
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    service = MemoryService(Session(engine), provider=CountingEmbeddingProvider(dimensions=7))
    with pytest.raises(DomainError, match="dimension"):
        service.create_memory(
            MemoryCreate(
                memory_type="SYSTEM_OBSERVATION",
                scope="RUN",
                content="Wrong dimensions fail closed.",
                source="test",
                source_type="SYSTEM_OBSERVATION",
                source_id="wrong-dimension",
                confidence=0.8,
                importance=0.5,
            )
        )


def test_graph_runtime_uses_resolved_embedding_provider(monkeypatch: pytest.MonkeyPatch) -> None:
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    session = Session(engine)
    provider = CountingEmbeddingProvider()
    monkeypatch.setattr(workflow_module, "resolve_embedding_provider", lambda: provider)
    mission = Mission(
        mission_id="RESOLVER-MISSION",
        mission_type=MissionType.PERIMETER_INSPECTION,
        priority=Priority.HIGH,
        target_latitude=1,
        target_longitude=1,
        objective="resolver test",
        status=MissionStatus.PLANNED,
    )
    drone = Drone(
        drone_id="DR-RESOLVER",
        name="Resolver drone",
        status=DroneStatus.AVAILABLE,
        latitude=1,
        longitude=1,
        battery_percentage=80,
        temperature=20,
        gps_accuracy=1,
        health_status=HealthStatus.HEALTHY,
    )
    session.add_all([mission, drone])
    session.flush()
    event = Event(
        event_id="RESOLVER-EVENT",
        mission_id=mission.id,
        drone_id=drone.id,
        event_type=EventType.INTRUSION,
        severity=Priority.HIGH,
        confidence=0.9,
        description="Simulated resolver event",
        metadata_={"simulated": True},
    )
    session.add(event)
    session.commit()
    result = workflow_module.build_workflow(session).invoke(
        {
            "request_id": str(uuid4()),
            "run_id": str(uuid4()),
            "incoming_event": event,
            "mission_context": mission,
            "drone_context": drone,
            "execute_tools": False,
        }
    )
    assert result["memory_context"] == []
    # Knowledge and memory retrieval both used the provider resolved at graph construction.
    assert len(provider.calls) >= 2
