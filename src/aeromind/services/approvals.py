from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy.orm import Session

from aeromind.models.domain import Approval
from aeromind.tools.definitions import ToolCall
from aeromind.tools.executor import ToolExecutor


class ApprovalService:
    def __init__(self, session: Session) -> None:
        self.session = session

    def create(
        self,
        tool_name: str,
        payload: dict[str, object],
        run_id: str | None,
        ttl_seconds: int = 300,
    ) -> Approval:
        item = Approval(
            status="PENDING",
            tool_name=tool_name,
            payload={"call": payload, "run_id": run_id},
            expires_at=datetime.now(UTC) + timedelta(seconds=ttl_seconds),
        )
        self.session.add(item)
        self.session.flush()
        return item

    def transition(self, approval_id: UUID, status: str) -> Approval:
        item = self.session.get(Approval, approval_id)
        if not item:
            raise ValueError("Approval not found")

        now = datetime.now(UTC)
        expires_at = item.expires_at
        if expires_at is not None and expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=UTC)

        if item.status == "PENDING" and expires_at and expires_at <= now:
            item.status = "EXPIRED"
            self.session.flush()
            raise ValueError("Approval has expired")

        if item.status != "PENDING" or status not in {"APPROVED", "REJECTED", "EXPIRED"}:
            raise ValueError("Invalid approval transition")

        item.status = status
        self.session.flush()

        return item

    def approve_and_execute(self, approval_id: UUID) -> tuple[Approval, object]:
        item = self.transition(approval_id, "APPROVED")
        call_data = item.payload.get("call")
        if not isinstance(call_data, dict) or item.tool_name is None:
            raise ValueError("Invalid approval payload")
        result = ToolExecutor(self.session).execute(
            ToolCall(name=item.tool_name, arguments=call_data, request_id="approval"),
            item.payload.get("run_id"),
            approval_id=str(item.id),
        )
        return item, result
