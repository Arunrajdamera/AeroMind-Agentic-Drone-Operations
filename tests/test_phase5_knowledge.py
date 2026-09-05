from __future__ import annotations

import asyncio

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from aeromind.agents.knowledge import KnowledgeAgent
from aeromind.api.routes.knowledge import get_session
from aeromind.core.exceptions import DomainError
from aeromind.db.base import Base
from aeromind.main import create_app
from aeromind.providers.interfaces import EmbeddingProvider
from aeromind.providers.mock import MockEmbeddingProvider
from aeromind.schemas.knowledge import DocumentIngestRequest
from aeromind.services.knowledge import DeterministicChunker, KnowledgeService


def knowledge_client() -> tuple[TestClient, Session]:
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    session = Session(engine)
    app = create_app()
    app.dependency_overrides[get_session] = lambda: session
    return TestClient(app), session


def test_chunker_is_deterministic_and_preserves_overlap() -> None:
    chunker = DeterministicChunker(chunk_size=5, overlap=2, max_chunks=10)
    assert chunker.chunk("abcdefghij") == ["abcde", "defgh", "ghij"]
    assert chunker.chunk("  alpha\n beta ") == ["alpha", "ha be", "beta"]
    assert chunker.chunk("   ") == []
    with pytest.raises(DomainError, match="chunk limit"):
        DeterministicChunker(chunk_size=3, overlap=1, max_chunks=1).chunk("abcdef")


class BadCountProvider(EmbeddingProvider):
    async def embed(self, texts: list[str]) -> list[list[float]]:
        del texts
        return []


class BadDimensionProvider(EmbeddingProvider):
    async def embed(self, texts: list[str]) -> list[list[float]]:
        return [[0.0] for _ in texts]


def test_mock_embedding_is_deterministic_and_provider_results_are_validated() -> None:
    first = asyncio.run(MockEmbeddingProvider().embed(["solar farm"]))
    second = asyncio.run(MockEmbeddingProvider().embed(["solar farm"]))
    assert first == second and len(first[0]) == 8
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    request = DocumentIngestRequest(title="x", content="content", source="test")
    with pytest.raises(DomainError, match="count"):
        KnowledgeService(Session(engine), provider=BadCountProvider()).ingest(request)
    with pytest.raises(DomainError, match="dimension"):
        KnowledgeService(Session(engine), provider=BadDimensionProvider()).ingest(request)


def test_ingestion_retrieval_provenance_duplicate_and_empty_corpus() -> None:
    client, _ = knowledge_client()
    assert (
        client.post("/knowledge/search", json={"query": "intrusion"}).json()["retrieved_chunks"]
        == []
    )
    payload = {
        "title": "Restricted zone procedure",
        "content": "Restricted-zone intrusion requires simulated security escalation.",
        "source": "policy://restricted-zone",
        "metadata": {"policy": "restricted-zone", "revision": 1},
    }
    created = client.post("/knowledge/documents", json=payload)
    duplicate = client.post("/knowledge/documents", json=payload)
    result = client.post("/knowledge/search", json={"query": payload["content"], "top_k": 1})
    assert created.status_code == 201 and created.json()["chunk_count"] == 1
    assert duplicate.status_code == 201 and not duplicate.json()["created"]
    assert result.status_code == 200
    chunk = result.json()["retrieved_chunks"][0]
    assert chunk["source"] == payload["source"]
    assert chunk["metadata"]["policy"] == "restricted-zone"
    assert chunk["similarity_score"] == 1.0


def test_knowledge_agent_returns_persisted_evidence_without_fabricating_policy() -> None:
    _, session = knowledge_client()
    service = KnowledgeService(session)
    agent = KnowledgeAgent(service=service)
    state = {
        "incoming_event": type(
            "Event", (), {"event_type": type("Type", (), {"value": "INTRUSION"})}
        )()
    }
    empty = agent.run(state)["knowledge_result"]
    assert not empty.relevant and empty.sources == []
    service.ingest(
        DocumentIngestRequest(
            title="Intrusion", content="INTRUSION procedures are simulated.", source="policy://test"
        )
    )
    retrieved = agent.run(state)["knowledge_result"]
    assert retrieved.relevant and retrieved.sources == ["policy://test"]
    assert retrieved.retrieved_chunks[0]["source"] == "policy://test"
