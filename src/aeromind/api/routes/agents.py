# ruff: noqa: B008
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from aeromind.core.exceptions import DomainError
from aeromind.db.session import get_session
from aeromind.models.domain import AgentRun, ToolExecution
from aeromind.services.orchestrator import AgentOrchestrator

router = APIRouter(prefix="/agent", tags=["agents"])


class RunRequest(BaseModel):
    event_id: str
    mission_id: str | None = None
    drone_id: str | None = None
    execute_tools: bool = False


@router.post("/run")
def run(data: RunRequest, session: Session = Depends(get_session)) -> dict:
    try:
        result = AgentOrchestrator(session).run_event_analysis(
            data.event_id, data.mission_id, data.drone_id, data.execute_tools
        )
        return {
            "run_id": result["run_id"],
            "decision": result.get("decision"),
            "risk_assessment": result.get("risk_assessment"),
            "mission_plan": result.get("mission_plan"),
            "perception": result.get("perception_result"),
            "knowledge": result.get("knowledge_result"),
            "memory_context": result.get("memory_context", []),
            "recorded_memory_ids": result.get("recorded_memory_ids", []),
            "warnings": result.get("warnings", []),
            "tool_requests": result.get("tool_requests", []),
            "tool_results": result.get("tool_results", []),
            "errors": result.get("errors", []),
            "execution_status": result["execution_status"],
        }
    except DomainError as error:
        raise HTTPException(404, str(error)) from error


@router.get("/runs/{run_id}")
def get_run(run_id: str, session: Session = Depends(get_session)) -> dict:
    record = session.query(AgentRun).filter_by(run_id=run_id).one_or_none()
    if not record:
        raise HTTPException(404, "Agent run not found")
    return {
        "run_id": record.run_id,
        "status": record.status,
        "execution_status": record.execution_status,
        "final_decision": record.final_decision,
        "error": record.error,
        "payload": record.payload,
    }


@router.get("/runs/{run_id}/tools")
def get_tools(run_id: str, session: Session = Depends(get_session)) -> list[dict]:
    record = session.query(AgentRun).filter_by(run_id=run_id).one_or_none()
    if not record:
        raise HTTPException(404, "Agent run not found")
    return [
        {"tool_name": x.tool_name, "status": x.status, "payload": x.payload}
        for x in session.query(ToolExecution).filter_by(run_id=record.id)
    ]
