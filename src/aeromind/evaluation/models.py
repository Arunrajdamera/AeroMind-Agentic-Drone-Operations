from __future__ import annotations

from enum import StrEnum

from pydantic import Field

from aeromind.models.domain import DroneStatus, EventType, Priority
from aeromind.schemas.agents import RecommendedAction, RiskLevel
from aeromind.schemas.common import DomainModel


class ScenarioKind(StrEnum):
    WORKFLOW = "WORKFLOW"
    TOOL_EXECUTOR = "TOOL_EXECUTOR"


class ScenarioExpectation(DomainModel):
    decision: RecommendedAction | None = None
    risk_level: RiskLevel | None = None
    approval_required: bool | None = None
    tool_path: bool
    tools: list[str] = Field(default_factory=list)
    execution_status: str | None = None
    approval_created: bool | None = None
    drone_status: DroneStatus | None = None
    minimum_evidence_strength: float | None = Field(default=None, ge=0, le=1)


class EvaluationScenario(DomainModel):
    scenario_id: str = Field(pattern=r"^[a-z0-9_]+$")
    description: str = Field(min_length=1, max_length=500)
    kind: ScenarioKind = ScenarioKind.WORKFLOW
    event_type: EventType = EventType.BATTERY_WARNING
    severity: Priority = Priority.LOW
    event_confidence: float = Field(default=0.5, ge=0, le=1)
    event_metadata: dict[str, str | bool | int | float] = Field(default_factory=dict)
    execute_tools: bool = True
    expected: ScenarioExpectation
    approve_pending_action: bool = False
    seed_strong_evidence: bool = False
    evaluation_decision_override: RecommendedAction | None = None


class EvaluationAssertion(DomainModel):
    name: str
    passed: bool
    expected: str | bool | float | list[str] | None
    actual: str | bool | float | list[str] | None


class EvaluationResult(DomainModel):
    scenario_id: str
    passed: bool
    assertions: list[EvaluationAssertion]
    expected_decision: RecommendedAction | None = None
    actual_decision: RecommendedAction | None = None
    expected_risk_level: RiskLevel | None = None
    actual_risk_level: RiskLevel | None = None
    expected_approval_required: bool | None = None
    actual_approval_required: bool | None = None
    expected_tools: list[str] = Field(default_factory=list)
    actual_tools: list[str] = Field(default_factory=list)
    final_execution_status: str | None = None
    elapsed_ms: float = Field(ge=0)
