# ruff: noqa: B008
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from aeromind.core.exceptions import DomainError
from aeromind.db.session import get_session
from aeromind.schemas.knowledge import (
    DocumentIngestRequest,
    DocumentIngestResult,
    KnowledgeSearchRequest,
    KnowledgeSearchResult,
)
from aeromind.services.knowledge import KnowledgeService

router = APIRouter(prefix="/knowledge", tags=["knowledge"])


@router.post("/documents", response_model=DocumentIngestResult, status_code=201)
def ingest_document(
    data: DocumentIngestRequest, session: Session = Depends(get_session)
) -> DocumentIngestResult:
    try:
        result = KnowledgeService(session).ingest(data)
        return result
    except DomainError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


@router.post("/search", response_model=KnowledgeSearchResult)
def search_knowledge(
    data: KnowledgeSearchRequest, session: Session = Depends(get_session)
) -> KnowledgeSearchResult:
    try:
        return KnowledgeService(session).search(data.query, data.top_k, data.similarity_threshold)
    except DomainError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
