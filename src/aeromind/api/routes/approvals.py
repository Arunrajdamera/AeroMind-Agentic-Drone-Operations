from __future__ import annotations

# ruff: noqa: B008  # FastAPI dependency declarations use Depends in signatures.
import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from aeromind.db.session import get_session
from aeromind.models.domain import Approval
from aeromind.providers.resolver import resolve_embedding_provider
from aeromind.schemas.api import ApprovalActionRead, ApprovalExecutionMetadata, ApprovalRead
from aeromind.services.approvals import ApprovalService
from aeromind.services.memory import MemoryService
from aeromind.tools.definitions import ToolStatus

router = APIRouter(prefix="/approvals", tags=["approvals"])
logger = logging.getLogger(__name__)


def response(item: Approval) -> ApprovalRead:
    return ApprovalRead(approval_id=str(item.id), status=item.status, tool_name=item.tool_name)


def _record_terminal_outcome(session: Session, item: Approval, execution: object = None) -> None:
    """Best-effort downstream evidence; never changes the approval or tool result."""
    try:
        MemoryService(session, provider=resolve_embedding_provider()).record_approval_outcome(
            item, execution
        )
        session.commit()
    except Exception as error:
        session.rollback()
        logger.error(
            "memory.approval_outcome",
            extra={
                "operation": "memory.approval_outcome",
                "success": False,
                "error_type": type(error).__name__,
                "tool_name": item.tool_name,
            },
        )


def _record_expiry_if_transitioned(session: Session, approval_id: UUID) -> None:
    item = session.get(Approval, approval_id)
    if item and item.status == "EXPIRED":
        session.commit()
        _record_terminal_outcome(session, item)


@router.get("", response_model=list[ApprovalRead])
def list_approvals(session: Session = Depends(get_session)) -> list[ApprovalRead]:
    return [response(x) for x in session.query(Approval).all()]


@router.post("/{approval_id}/approve", response_model=ApprovalActionRead)
def approve(approval_id: UUID, session: Session = Depends(get_session)) -> ApprovalActionRead:
    try:
        item, result = ApprovalService(session).approve_and_execute(approval_id)
        session.commit()
        _record_terminal_outcome(session, item, result)
        if result.status != ToolStatus.SUCCEEDED:
            raise HTTPException(409, "Approved tool execution failed")
        return ApprovalActionRead(
            **response(item).model_dump(),
            execution=ApprovalExecutionMetadata(
                tool_name=result.tool_name, status=result.status.value
            ),
        )
    except ValueError as error:
        _record_expiry_if_transitioned(session, approval_id)
        raise HTTPException(409, str(error)) from error


@router.post("/{approval_id}/reject", response_model=ApprovalActionRead)
def reject(approval_id: UUID, session: Session = Depends(get_session)) -> ApprovalActionRead:
    try:
        item = ApprovalService(session).transition(approval_id, "REJECTED")
        session.commit()
        _record_terminal_outcome(session, item)
        return ApprovalActionRead(**response(item).model_dump())
    except ValueError as error:
        _record_expiry_if_transitioned(session, approval_id)
        raise HTTPException(409, str(error)) from error


@router.post("/{approval_id}/expire", response_model=ApprovalActionRead)
def expire(approval_id: UUID, session: Session = Depends(get_session)) -> ApprovalActionRead:
    try:
        item = ApprovalService(session).transition(approval_id, "EXPIRED")
        session.commit()
        _record_terminal_outcome(session, item)
        return ApprovalActionRead(**response(item).model_dump())
    except ValueError as error:
        _record_expiry_if_transitioned(session, approval_id)
        raise HTTPException(409, str(error)) from error
