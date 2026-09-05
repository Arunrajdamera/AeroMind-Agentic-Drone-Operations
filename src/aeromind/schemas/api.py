from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from aeromind.models.domain import (
    DroneStatus,
    EventType,
    HealthStatus,
    MissionStatus,
    MissionType,
    Priority,
    Severity,
)
from aeromind.schemas.agents import DecisionFactors, RecommendedAction, RiskLevel


class ApiModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class DroneCreate(ApiModel):
    drone_id: str
    name: str
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    altitude: float = Field(default=0, ge=0)
    current_speed: float = Field(default=0, ge=0)
    battery_percentage: float = Field(ge=0, le=100)
    temperature: float
    gps_accuracy: float = Field(ge=0)
    health_status: HealthStatus = HealthStatus.HEALTHY


class DroneUpdate(ApiModel):
    status: DroneStatus | None = None
    battery_percentage: float | None = Field(default=None, ge=0, le=100)
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)


class DroneRead(DroneCreate):
    status: DroneStatus
    last_seen: datetime


class MissionCreate(ApiModel):
    mission_id: str
    mission_type: MissionType
    priority: Priority
    target_latitude: float = Field(ge=-90, le=90)
    target_longitude: float = Field(ge=-180, le=180)
    objective: str


class MissionRead(MissionCreate):
    status: MissionStatus
    assigned_drone_id: str | None = None


class TelemetryCreate(ApiModel):
    drone_id: str
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    altitude: float = Field(ge=0)
    speed: float = Field(ge=0)
    battery_percentage: float = Field(ge=0, le=100)
    temperature: float
    gps_accuracy: float = Field(ge=0)
    health_status: HealthStatus


class TelemetryRead(TelemetryCreate):
    timestamp: datetime


class EventCreate(ApiModel):
    event_id: str
    event_type: EventType
    severity: Severity
    confidence: float = Field(ge=0, le=1)
    description: str
    drone_id: str | None = None
    mission_id: str | None = None
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)
    metadata: dict[str, Any] = Field(default_factory=dict)


class EventRead(EventCreate):
    created_at: datetime


class TelemetryHealth(ApiModel):
    healthy: bool
    warnings: list[str]


class AgentRunRequest(ApiModel):
    event_id: str
    mission_id: str | None = None
    drone_id: str | None = None
    execute_tools: bool = False


class MissionPlanMetadata(ApiModel):
    selected_drone_id: str | None = None
    mission_type: str
    priority: str
    planned_action: RecommendedAction
    constraint_count: int = Field(ge=0)


class PerceptionMetadata(ApiModel):
    event_type: str
    object_type: str
    confidence: float = Field(ge=0, le=1)
    severity: str
    restricted_zone: bool
    requires_investigation: bool


class RiskAssessmentMetadata(ApiModel):
    risk_level: RiskLevel
    risk_score: float = Field(ge=0, le=100)
    recommended_action: RecommendedAction
    requires_human_approval: bool


class KnowledgeMetadata(ApiModel):
    relevant: bool
    confidence: float = Field(ge=0, le=1)
    source_count: int = Field(ge=0)


class DecisionMetadata(ApiModel):
    decision: RecommendedAction
    confidence: float = Field(ge=0, le=1)
    actions: list[str] = Field(default_factory=list)
    requires_approval: bool
    decision_factors: DecisionFactors | None = None


class ToolRequestMetadata(ApiModel):
    name: str


class ToolExecutionMetadata(ApiModel):
    tool_name: str
    status: str


class AgentRunResponse(ApiModel):
    run_id: str
    decision: DecisionMetadata | None = None
    risk_assessment: RiskAssessmentMetadata | None = None
    mission_plan: MissionPlanMetadata | None = None
    perception: PerceptionMetadata | None = None
    knowledge: KnowledgeMetadata | None = None
    memory_count: int = Field(ge=0)
    recorded_memory_ids: list[str] = Field(default_factory=list)
    warning_count: int = Field(ge=0)
    tool_requests: list[ToolRequestMetadata] = Field(default_factory=list)
    tool_results: list[ToolExecutionMetadata] = Field(default_factory=list)
    error_types: list[str] = Field(default_factory=list)
    execution_status: str


class AgentRunRead(ApiModel):
    run_id: str
    status: str
    execution_status: str
    final_decision: str | None = None
    error_type: str | None = None
    requested_tool_names: list[str] = Field(default_factory=list)
    requested_tool_count: int = Field(ge=0)


class AgentToolExecutionRead(ApiModel):
    tool_name: str
    status: str


class ApprovalRead(ApiModel):
    approval_id: str
    status: str
    tool_name: str | None = None


class ApprovalExecutionMetadata(ApiModel):
    tool_name: str
    status: str


class ApprovalActionRead(ApprovalRead):
    execution: ApprovalExecutionMetadata | None = None
