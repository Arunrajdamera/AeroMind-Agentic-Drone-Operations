# ruff: noqa: B008
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from aeromind.core.exceptions import DomainError
from aeromind.db.session import get_session
from aeromind.models.domain import MemoryStatus
from aeromind.providers.resolver import resolve_embedding_provider
from aeromind.schemas.memory import MemoryCreate, MemoryRead, MemorySearch, MemorySearchResult
from aeromind.services.memory import MemoryService

router = APIRouter(prefix="/memory", tags=["memory"])


def _service(session: Session) -> MemoryService:
    return MemoryService(session, provider=resolve_embedding_provider())


def _read(service: MemoryService, memory_id: UUID) -> MemoryRead:
    item = service.get_memory(memory_id)
    if item is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Memory was not found")
    return service.as_read(item)


@router.post("", response_model=MemoryRead, status_code=status.HTTP_201_CREATED)
def create_memory(data: MemoryCreate, session: Session = Depends(get_session)) -> MemoryRead:
    try:
        service = _service(session)
        item, _ = service.create_memory(data)
        session.commit()
        return service.as_read(item)
    except DomainError as error:
        session.rollback()
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(error)) from error


@router.post("/search", response_model=MemorySearchResult)
def search_memory(
    data: MemorySearch, session: Session = Depends(get_session)
) -> MemorySearchResult:
    try:
        result = _service(session).retrieve_memories(data)
        session.commit()
        return result
    except DomainError as error:
        session.rollback()
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(error)) from error


@router.get("/{memory_id}", response_model=MemoryRead)
def get_memory(memory_id: UUID, session: Session = Depends(get_session)) -> MemoryRead:
    return _read(_service(session), memory_id)


@router.post("/{memory_id}/archive", response_model=MemoryRead)
def archive_memory(memory_id: UUID, session: Session = Depends(get_session)) -> MemoryRead:
    try:
        service = _service(session)
        service.update_memory_status(memory_id, MemoryStatus.ARCHIVED)
        session.commit()
        return _read(service, memory_id)
    except DomainError as error:
        session.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, str(error)) from error


@router.post("/{memory_id}/invalidate", response_model=MemoryRead)
def invalidate_memory(memory_id: UUID, session: Session = Depends(get_session)) -> MemoryRead:
    try:
        service = _service(session)
        service.update_memory_status(memory_id, MemoryStatus.INVALIDATED)
        session.commit()
        return _read(service, memory_id)
    except DomainError as error:
        session.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, str(error)) from error
