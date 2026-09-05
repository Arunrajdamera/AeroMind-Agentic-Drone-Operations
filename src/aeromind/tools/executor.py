from __future__ import annotations

from datetime import UTC, datetime, timedelta
from time import perf_counter
from uuid import UUID, uuid4

from pydantic import ValidationError
from sqlalchemy.orm import Session

from aeromind.models.domain import AgentRun, Approval, ToolExecution
from aeromind.safety.policy import ToolSafetyPolicy
from aeromind.tools.catalog import ToolCatalog, build_catalog
from aeromind.tools.definitions import (
    ToolCall,
    ToolExecutionResult,
    ToolStatus,
)


class ToolExecutor:
    def __init__(
        self,
        session: Session,
        policy: ToolSafetyPolicy | None = None,
        catalog: ToolCatalog | None = None,
    ) -> None:
        self.session = session
        self.policy = policy or ToolSafetyPolicy()
        self.catalog = catalog or build_catalog(session)

    def execute(
        self,
        call: ToolCall,
        run_id: str | None = None,
        approval_id: str | None = None,
    ) -> ToolExecutionResult:
        started = perf_counter()
        execution_id = str(uuid4())

        definition = self.catalog.get(call.name)
        if definition is None:
            return self._result(
                execution_id,
                call,
                run_id,
                ToolStatus.BLOCKED,
                started,
                error="Unknown tool",
            )

        try:
            validated = definition.input_schema.model_validate(call.arguments)
        except ValidationError:
            return self._result(
                execution_id,
                call,
                run_id,
                ToolStatus.FAILED,
                started,
                error="Invalid tool arguments",
            )

        allowed, approval, reason = self.policy.check(
            call.name,
            definition.risk,
        )
        approval_validated = False

        if definition.requires_approval or approval:
            if approval_id is None:
                approval_record = Approval(
                    status="PENDING",
                    tool_name=call.name,
                    payload={
                        "call": call.arguments,
                        "run_id": run_id,
                    },
                    expires_at=datetime.now(UTC) + timedelta(minutes=5),
                )
                self.session.add(approval_record)
                self.session.flush()

                return self._result(
                    execution_id,
                    call,
                    run_id,
                    ToolStatus.REQUIRES_APPROVAL,
                    started,
                    error=reason,
                    approval_id=str(approval_record.id),
                )

            try:
                approved_record = self.session.get(
                    Approval,
                    UUID(approval_id),
                )
            except (ValueError, AttributeError):
                approved_record = None

            if (
                approved_record is None
                or approved_record.status != "APPROVED"
                or approved_record.tool_name != call.name
                or approved_record.payload.get("call") != call.arguments
                or approved_record.payload.get("run_id") != run_id
            ):
                return self._result(
                    execution_id,
                    call,
                    run_id,
                    ToolStatus.BLOCKED,
                    started,
                    error="Invalid or unauthorized approval",
                    approval_id=approval_id,
                )
            approval_validated = True
        if not allowed and not approval_validated:
            return self._result(
                execution_id,
                call,
                run_id,
                ToolStatus.BLOCKED,
                started,
                error=reason,
            )

        try:
            result = definition.handler(validated)
            definition.output_schema.model_validate({"data": result})

            return self._result(
                execution_id,
                call,
                run_id,
                ToolStatus.SUCCEEDED,
                started,
                result,
                approval_id=approval_id,
            )
        except (ValidationError, ValueError):
            return self._result(
                execution_id,
                call,
                run_id,
                ToolStatus.FAILED,
                started,
                error="Tool execution failed",
                approval_id=approval_id,
            )
        except Exception:
            return self._result(
                execution_id,
                call,
                run_id,
                ToolStatus.FAILED,
                started,
                error="Tool execution failed",
                approval_id=approval_id,
            )

    def _result(
        self,
        id_: str,
        call: ToolCall,
        run_id: str | None,
        status: ToolStatus,
        started: float,
        result: dict[str, object] | None = None,
        error: str | None = None,
        approval_id: str | None = None,
    ) -> ToolExecutionResult:
        value = ToolExecutionResult(
            execution_id=id_,
            tool_name=call.name,
            status=status,
            result=result or {},
            error=error,
            latency_ms=round(
                (perf_counter() - started) * 1000,
                3,
            ),
        )

        self.session.add(
            ToolExecution(
                tool_name=call.name,
                status=status.value,
                run_id=self._agent_run_id(run_id),
                payload={
                    "arguments": call.arguments,
                    "result": value.result,
                    "error": error,
                    "approval_id": approval_id,
                },
            )
        )
        self.session.flush()

        return value

    def _agent_run_id(
        self,
        public_run_id: str | None,
    ) -> UUID | None:
        if public_run_id is None:
            return None

        record = self.session.query(AgentRun).filter_by(run_id=public_run_id).one_or_none()

        return record.id if record else None
