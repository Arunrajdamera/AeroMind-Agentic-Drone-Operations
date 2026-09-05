from __future__ import annotations

from typing import TypedDict
from uuid import UUID

from aeromind.schemas.agents import (
    DecisionResult,
    EvidenceAssessment,
    KnowledgeResult,
    MissionPlan,
    PerceptionResult,
    RiskAssessment,
)
from aeromind.schemas.memory import MemoryEvidence


class AgentState(TypedDict, total=False):
    request_id: str
    run_id: str
    agent_run_id: UUID | None
    mission_id: str | None
    drone_id: str | None
    event_id: str | None
    incoming_event: object
    mission_context: object
    drone_context: object
    telemetry_context: object
    perception_image: bytes | None
    mission_plan: MissionPlan
    perception_result: PerceptionResult
    risk_assessment: RiskAssessment
    knowledge_result: KnowledgeResult
    memory_context: list[MemoryEvidence]
    evidence_assessment: EvidenceAssessment
    recorded_memory_ids: list[str]
    decision: DecisionResult
    tool_candidates: list[str]
    warnings: list[str]
    errors: list[str]
    execution_status: str
    tool_requests: list[object]
    tool_results: list[object]
    execute_tools: bool
