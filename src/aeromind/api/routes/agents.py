from __future__ import annotations

# ruff: noqa: B008  # FastAPI dependency declarations use Depends in signatures.
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from aeromind.core.exceptions import DomainError
from aeromind.db.session import get_session
from aeromind.models.domain import AgentRun, ToolExecution
from aeromind.schemas.api import (
    AgentRunRead,
    AgentRunRequest,
    AgentRunResponse,
    AgentToolExecutionRead,
    DecisionMetadata,
    KnowledgeMetadata,
    MissionPlanMetadata,
    PerceptionMetadata,
    RiskAssessmentMetadata,
    ToolExecutionMetadata,
    ToolRequestMetadata,
)
from aeromind.services.orchestrator import AgentOrchestrator
from aeromind.tools.catalog import build_catalog

router = APIRouter(prefix="/agent", tags=["agents"])


@router.post("/run", response_model=AgentRunResponse)
def run(data: AgentRunRequest, session: Session = Depends(get_session)) -> AgentRunResponse:
    try:
        result = AgentOrchestrator(session).run_event_analysis(
            data.event_id, data.mission_id, data.drone_id, data.execute_tools
        )
        return _run_response(result)
    except DomainError as error:
        raise HTTPException(404, str(error)) from error


@router.get("/runs/{run_id}", response_model=AgentRunRead)
def get_run(run_id: str, session: Session = Depends(get_session)) -> AgentRunRead:
    record = session.query(AgentRun).filter_by(run_id=run_id).one_or_none()
    if not record:
        raise HTTPException(404, "Agent run not found")
    requested_tools = _requested_tool_names(record.payload, session)
    return AgentRunRead(
        run_id=record.run_id,
        status=record.status,
        execution_status=record.execution_status,
        final_decision=record.final_decision,
        error_type=record.error,
        requested_tool_names=requested_tools,
        requested_tool_count=len(requested_tools),
    )


@router.get("/runs/{run_id}/tools", response_model=list[AgentToolExecutionRead])
def get_tools(run_id: str, session: Session = Depends(get_session)) -> list[AgentToolExecutionRead]:
    record = session.query(AgentRun).filter_by(run_id=run_id).one_or_none()
    if not record:
        raise HTTPException(404, "Agent run not found")
    executions = (
        session.query(ToolExecution).filter_by(run_id=record.id).order_by(ToolExecution.created_at)
    )
    return [
        AgentToolExecutionRead(tool_name=item.tool_name, status=item.status) for item in executions
    ]


def _run_response(result: dict[str, Any]) -> AgentRunResponse:
    decision = result.get("decision")
    risk = result.get("risk_assessment")
    plan = result.get("mission_plan")
    perception = result.get("perception_result")
    knowledge = result.get("knowledge_result")
    return AgentRunResponse(
        run_id=result["run_id"],
        decision=(
            DecisionMetadata(
                decision=decision.decision,
                confidence=decision.confidence,
                actions=decision.actions,
                requires_approval=decision.requires_approval,
                decision_factors=decision.decision_factors,
            )
            if decision
            else None
        ),
        risk_assessment=(
            RiskAssessmentMetadata(
                risk_level=risk.risk_level,
                risk_score=risk.risk_score,
                recommended_action=risk.recommended_action,
                requires_human_approval=risk.requires_human_approval,
            )
            if risk
            else None
        ),
        mission_plan=(
            MissionPlanMetadata(
                selected_drone_id=plan.selected_drone_id,
                mission_type=plan.mission_type,
                priority=plan.priority,
                planned_action=plan.planned_action,
                constraint_count=len(plan.constraints),
            )
            if plan
            else None
        ),
        perception=(
            PerceptionMetadata(
                event_type=perception.event_type,
                object_type=perception.object_type,
                confidence=perception.confidence,
                severity=perception.severity,
                restricted_zone=perception.restricted_zone,
                requires_investigation=perception.requires_investigation,
            )
            if perception
            else None
        ),
        knowledge=(
            KnowledgeMetadata(
                relevant=knowledge.relevant,
                confidence=knowledge.confidence,
                source_count=len(knowledge.sources),
            )
            if knowledge
            else None
        ),
        memory_count=len(result.get("memory_context", [])),
        recorded_memory_ids=[str(item) for item in result.get("recorded_memory_ids", [])],
        warning_count=len(result.get("warnings", [])),
        tool_requests=[
            ToolRequestMetadata(name=call.name) for call in result.get("tool_requests", [])
        ],
        tool_results=[
            ToolExecutionMetadata(tool_name=item.tool_name, status=item.status.value)
            for item in result.get("tool_results", [])
        ],
        error_types=_safe_error_types(result.get("errors", [])),
        execution_status=result["execution_status"],
    )


def _requested_tool_names(payload: object, session: Session) -> list[str]:
    if not isinstance(payload, dict):
        return []
    requested_tools = payload.get("requested_tools", [])
    if not isinstance(requested_tools, list):
        return []
    catalog = build_catalog(session)
    return [
        tool for tool in requested_tools if isinstance(tool, str) and catalog.get(tool) is not None
    ]


def _safe_error_types(errors: object) -> list[str]:
    if not isinstance(errors, list):
        return []
    return [
        error.removeprefix("workflow failure: ")
        for error in errors
        if isinstance(error, str) and error.startswith("workflow failure: ")
    ]
