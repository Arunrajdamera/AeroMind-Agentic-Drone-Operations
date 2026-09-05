from __future__ import annotations

import asyncio
import hashlib
import math
import re
from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.orm import Session

from aeromind.core.config import Settings, get_settings
from aeromind.core.exceptions import DomainError
from aeromind.models.domain import Document, DocumentChunk
from aeromind.providers.interfaces import EmbeddingProvider
from aeromind.providers.mock import MockEmbeddingProvider
from aeromind.schemas.knowledge import (
    DocumentIngestRequest,
    DocumentIngestResult,
    KnowledgeSearchResult,
    RetrievedChunk,
)


class DeterministicChunker:
    def __init__(self, chunk_size: int, overlap: int, max_chunks: int) -> None:
        if overlap >= chunk_size:
            raise ValueError("chunk overlap must be smaller than chunk size")
        self.chunk_size = chunk_size
        self.overlap = overlap
        self.max_chunks = max_chunks

    def chunk(self, content: str) -> list[str]:
        normalized = normalize_content(content)
        if not normalized:
            return []
        chunks: list[str] = []
        start = 0
        while start < len(normalized):
            if len(chunks) >= self.max_chunks:
                raise DomainError("Document exceeds the configured chunk limit")
            end = min(len(normalized), start + self.chunk_size)
            chunks.append(normalized[start:end])
            if end == len(normalized):
                break
            start = end - self.overlap
        return chunks


def normalize_content(content: str) -> str:
    return re.sub(r"\s+", " ", content).strip()


def _embed(provider: EmbeddingProvider, texts: list[str]) -> list[list[float]]:
    return asyncio.run(provider.embed(texts))


def _cosine_similarity(left: Sequence[float], right: Sequence[float]) -> float:
    dot = sum(a * b for a, b in zip(left, right, strict=True))
    left_norm = math.sqrt(sum(a * a for a in left))
    right_norm = math.sqrt(sum(b * b for b in right))
    return dot / (left_norm * right_norm) if left_norm and right_norm else 0.0


class KnowledgeRepository:
    """PostgreSQL uses pgvector; SQLite has a test-only deterministic fallback."""

    def __init__(self, session: Session, dimensions: int) -> None:
        self.session = session
        self.dimensions = dimensions

    def find_by_hash(self, content_hash: str) -> Document | None:
        return self.session.scalar(select(Document).where(Document.content_hash == content_hash))

    def create(self, document: Document, chunks: list[DocumentChunk]) -> None:
        self.session.add(document)
        self.session.flush()
        for chunk in chunks:
            chunk.document_id = document.id
        self.session.add_all(chunks)
        self.session.flush()

    def search(
        self, embedding: list[float], top_k: int, threshold: float
    ) -> list[tuple[DocumentChunk, Document, float]]:
        if len(embedding) != self.dimensions:
            raise DomainError(
                "Query embedding dimension does not match configured vector dimension"
            )
        if self.session.bind is not None and self.session.bind.dialect.name == "postgresql":
            distance = DocumentChunk.embedding.cosine_distance(embedding)
            rows = self.session.execute(
                select(DocumentChunk, Document, distance.label("distance"))
                .join(Document, Document.id == DocumentChunk.document_id)
                .order_by(distance)
                .limit(top_k)
            ).all()
            return [
                (chunk, document, 1.0 - float(distance))
                for chunk, document, distance in rows
                if 1.0 - float(distance) >= threshold
            ]

        # SQLite cannot execute pgvector operators. This is deliberately test-only.
        rows = self.session.execute(select(DocumentChunk, Document).join(Document)).all()
        scored = [
            (chunk, document, _cosine_similarity(embedding, chunk.embedding))
            for chunk, document in rows
        ]
        return sorted(
            (item for item in scored if item[2] >= threshold),
            key=lambda item: item[2],
            reverse=True,
        )[:top_k]


class KnowledgeService:
    def __init__(
        self,
        session: Session,
        provider: EmbeddingProvider | None = None,
        settings: Settings | None = None,
    ) -> None:
        self.session = session
        self.settings = settings or get_settings()
        self.provider = provider or MockEmbeddingProvider()
        self.repository = KnowledgeRepository(session, self.settings.embedding_dimensions)
        self.chunker = DeterministicChunker(
            self.settings.knowledge_chunk_size,
            self.settings.knowledge_chunk_overlap,
            self.settings.knowledge_max_chunks_per_document,
        )

    def ingest(self, request: DocumentIngestRequest) -> DocumentIngestResult:
        content = normalize_content(request.content)
        if not content:
            raise DomainError("Document content must not be empty")
        if len(content) > self.settings.knowledge_max_document_chars:
            raise DomainError("Document exceeds the configured character limit")
        content_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()
        existing = self.repository.find_by_hash(content_hash)
        if existing:
            return DocumentIngestResult(
                document_id=existing.id,
                content_hash=existing.content_hash,
                chunk_count=len(existing.chunks),
                created=False,
            )
        pieces = self.chunker.chunk(content)
        embeddings = _embed(self.provider, pieces)
        self._validate_embeddings(embeddings, len(pieces))
        document = Document(
            title=request.title.strip(),
            content=content,
            source=request.source.strip(),
            external_reference=request.external_reference,
            content_hash=content_hash,
            metadata_=request.metadata,
        )
        chunks = [
            DocumentChunk(
                document_id=document.id,
                chunk_index=index,
                content=piece,
                metadata_=request.metadata,
                embedding=embedding,
                embedding_model=self.settings.embedding_model_name,
            )
            for index, (piece, embedding) in enumerate(zip(pieces, embeddings, strict=True))
        ]
        try:
            self.repository.create(document, chunks)
            self.session.commit()
        except Exception:
            self.session.rollback()
            raise
        return DocumentIngestResult(
            document_id=document.id,
            content_hash=content_hash,
            chunk_count=len(chunks),
            created=True,
        )

    def search(
        self, query: str, top_k: int | None = None, threshold: float | None = None
    ) -> KnowledgeSearchResult:
        query = normalize_content(query)
        if not query:
            raise DomainError("Knowledge query must not be empty")
        embeddings = _embed(self.provider, [query])
        self._validate_embeddings(embeddings, 1)
        rows = self.repository.search(
            embeddings[0],
            top_k or self.settings.knowledge_default_top_k,
            self.settings.knowledge_similarity_threshold if threshold is None else threshold,
        )
        retrieved = [
            RetrievedChunk(
                document_id=document.id,
                chunk_id=chunk.id,
                source=document.source,
                similarity_score=round(score, 6),
                metadata={**document.metadata_, **chunk.metadata_},
                content_excerpt=chunk.content[:500],
            )
            for chunk, document, score in rows
        ]
        if not retrieved:
            return KnowledgeSearchResult(
                answer="No relevant knowledge documents were retrieved.", confidence=0.0
            )
        return KnowledgeSearchResult(
            answer="Retrieved operational knowledge is available from the cited sources.",
            confidence=min(1.0, max(0.0, retrieved[0].similarity_score)),
            sources=list(dict.fromkeys(item.source for item in retrieved)),
            retrieved_chunks=retrieved,
        )

    def _validate_embeddings(self, embeddings: list[list[float]], expected_count: int) -> None:
        if len(embeddings) != expected_count:
            raise DomainError("Embedding provider returned an unexpected embedding count")
        if any(len(vector) != self.settings.embedding_dimensions for vector in embeddings):
            raise DomainError("Embedding provider returned an unexpected embedding dimension")
