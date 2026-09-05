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
