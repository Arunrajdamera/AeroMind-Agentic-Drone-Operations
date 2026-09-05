from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, Field


class ToolRisk(StrEnum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


class ToolStatus(StrEnum):
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    BLOCKED = "BLOCKED"
    REQUIRES_APPROVAL = "REQUIRES_APPROVAL"


class ToolCall(BaseModel):
    name: str
    arguments: dict[str, object] = Field(default_factory=dict)
    request_id: str


class ToolExecutionResult(BaseModel):
    execution_id: str
    tool_name: str
    status: ToolStatus
    result: dict[str, object] = Field(default_factory=dict)
    error: str | None = None
    latency_ms: float = 0


class DroneIdInput(BaseModel):
    drone_id: str


class DistanceInput(BaseModel):
    latitude_a: float = Field(ge=-90, le=90)
    longitude_a: float = Field(ge=-180, le=180)
    latitude_b: float = Field(ge=-90, le=90)
    longitude_b: float = Field(ge=-180, le=180)


class TelemetryAnalysisInput(BaseModel):
    drone_id: str
    window_minutes: int = Field(default=60, ge=1, le=1440)


class MissionIdInput(BaseModel):
    mission_id: str


class DispatchInput(BaseModel):
    drone_id: str
    mission_id: str


class CaptureInput(BaseModel):
    drone_id: str


class AlertInput(BaseModel):
    description: str
    drone_id: str | None = None


class MissionUpdateInput(BaseModel):
    mission_id: str
    status: str


class TelemetryInput(BaseModel):
    drone_id: str
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    altitude: float = Field(default=0, ge=0)
    speed: float = Field(default=0, ge=0)
    battery_percentage: float = Field(ge=0, le=100)
    temperature: float
    gps_accuracy: float = Field(ge=0)
