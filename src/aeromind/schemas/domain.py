from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any
from uuid import UUID

from pydantic import Field, field_validator

from aeromind.schemas.common import DomainModel, TimestampedModel


class DroneStatus(StrEnum):
    AVAILABLE = "available"
    ACTIVE = "active"
    OFFLINE = "offline"
    MAINTENANCE = "maintenance"


class MissionStatus(StrEnum):
    DRAFT = "draft"
    PENDING = "pending"
    ACTIVE = "active"
    COMPLETED = "completed"
    ABORTED = "aborted"


class ApprovalStatus(StrEnum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXPIRED = "expired"


class ExecutionStatus(StrEnum):
    PENDING = "pending"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    BLOCKED = "blocked"


class Coordinates(DomainModel):
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    altitude_m: float | None = Field(default=None, ge=0)


class Drone(TimestampedModel):
    drone_id: str = Field(min_length=1, max_length=64)
    status: DroneStatus
    location: Coordinates
    battery_percent: float = Field(ge=0, le=100)
    health_score: float = Field(ge=0, le=1)


class Mission(TimestampedModel):
    mission_id: str = Field(min_length=1, max_length=64)
    status: MissionStatus = MissionStatus.DRAFT
    objective: str = Field(min_length=1, max_length=1000)
    priority: int = Field(ge=1, le=5)
    assigned_drone_id: str | None = None


class Telemetry(TimestampedModel):
    drone_id: str
    observed_at: datetime
    location: Coordinates
    battery_percent: float = Field(ge=0, le=100)
    gps_accuracy_m: float = Field(ge=0)
    metrics: dict[str, float] = Field(default_factory=dict)


class Event(TimestampedModel):
    event_type: str = Field(min_length=1, max_length=100)
    severity: int = Field(ge=1, le=5)
    location: Coordinates | None = None
    payload: dict[str, Any] = Field(default_factory=dict)


class Approval(TimestampedModel):
    mission_id: str
    action: str
    risk_level: str
    reason: str
    status: ApprovalStatus = ApprovalStatus.PENDING
    approved_by: str | None = None
    approved_at: datetime | None = None


class AgentRun(TimestampedModel):
    run_id: str
    agent_name: str
    status: ExecutionStatus = ExecutionStatus.PENDING
    input_summary: str
    output_summary: str | None = None


class ToolExecution(TimestampedModel):
    tool_name: str
    status: ExecutionStatus = ExecutionStatus.PENDING
    request_id: str
    mission_id: str | None = None
    result_summary: str | None = None


class ToolRequest(DomainModel):
    tool_name: str
    arguments: dict[str, Any] = Field(default_factory=dict)

    @field_validator("tool_name")
    @classmethod
    def tool_name_is_identifier(cls, value: str) -> str:
        if not value.isidentifier():
            raise ValueError("tool_name must be a Python-style identifier")
        return value


class ToolResult(DomainModel):
    status: ExecutionStatus
    tool_name: str
    message: str
    data: dict[str, Any] = Field(default_factory=dict)
    execution_id: UUID | None = None
