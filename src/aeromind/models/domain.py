from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any
from uuid import UUID, uuid4

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    JSON,
    CheckConstraint,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Index,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func
from sqlalchemy.types import Uuid

from aeromind.db.base import Base

JsonType = JSON().with_variant(JSONB, "postgresql")


class DroneStatus(StrEnum):
    AVAILABLE = "AVAILABLE"
    DEPLOYED = "DEPLOYED"
    IN_MISSION = "IN_MISSION"
    RETURNING = "RETURNING"
    CHARGING = "CHARGING"
    OFFLINE = "OFFLINE"
    EMERGENCY = "EMERGENCY"


class HealthStatus(StrEnum):
    HEALTHY = "HEALTHY"
    DEGRADED = "DEGRADED"
    CRITICAL = "CRITICAL"


class MissionType(StrEnum):
    PERIMETER_INSPECTION = "PERIMETER_INSPECTION"
    SECURITY_PATROL = "SECURITY_PATROL"
    INFRASTRUCTURE_INSPECTION = "INFRASTRUCTURE_INSPECTION"
    THERMAL_INSPECTION = "THERMAL_INSPECTION"
    INCIDENT_RESPONSE = "INCIDENT_RESPONSE"


class MissionStatus(StrEnum):
    PLANNED = "PLANNED"
    ASSIGNED = "ASSIGNED"
    IN_PROGRESS = "IN_PROGRESS"
    PAUSED = "PAUSED"
    COMPLETED = "COMPLETED"
    ABORTED = "ABORTED"
    FAILED = "FAILED"


class Priority(StrEnum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class EventType(StrEnum):
    INTRUSION = "INTRUSION"
    SUSPICIOUS_PERSON = "SUSPICIOUS_PERSON"
    UNAUTHORIZED_VEHICLE = "UNAUTHORIZED_VEHICLE"
    THERMAL_ANOMALY = "THERMAL_ANOMALY"
    GPS_ANOMALY = "GPS_ANOMALY"
    BATTERY_WARNING = "BATTERY_WARNING"
    SEVERE_WEATHER = "SEVERE_WEATHER"
    EQUIPMENT_FAULT = "EQUIPMENT_FAULT"


Severity = Priority


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class Mission(Base, TimestampMixin):
    __tablename__ = "missions"
    __table_args__ = (Index("ix_missions_status", "status"),)
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    mission_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    mission_type: Mapped[MissionType] = mapped_column(Enum(MissionType, native_enum=False))
    priority: Mapped[Priority] = mapped_column(Enum(Priority, native_enum=False))
    target_latitude: Mapped[float] = mapped_column(Float)
    target_longitude: Mapped[float] = mapped_column(Float)
    assigned_drone_id: Mapped[UUID | None] = mapped_column(ForeignKey("drones.id"), nullable=True)
    status: Mapped[MissionStatus] = mapped_column(
        Enum(MissionStatus, native_enum=False), default=MissionStatus.PLANNED
    )
    objective: Mapped[str] = mapped_column(Text)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    assigned_drone: Mapped[Drone | None] = relationship(
        back_populates="assigned_mission", foreign_keys=[assigned_drone_id]
    )
    events: Mapped[list[Event]] = relationship(back_populates="mission")


class Drone(Base, TimestampMixin):
    __tablename__ = "drones"
    __table_args__ = (
        CheckConstraint(
            "battery_percentage >= 0 AND battery_percentage <= 100", name="ck_drone_battery"
        ),
        CheckConstraint("latitude >= -90 AND latitude <= 90", name="ck_drone_latitude"),
        CheckConstraint("longitude >= -180 AND longitude <= 180", name="ck_drone_longitude"),
    )
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    drone_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(128))
    status: Mapped[DroneStatus] = mapped_column(
        Enum(DroneStatus, native_enum=False), default=DroneStatus.AVAILABLE
    )
    latitude: Mapped[float] = mapped_column(Float)
    longitude: Mapped[float] = mapped_column(Float)
    altitude: Mapped[float] = mapped_column(Float, default=0)
    current_speed: Mapped[float] = mapped_column(Float, default=0)
    battery_percentage: Mapped[float] = mapped_column(Float)
    temperature: Mapped[float] = mapped_column(Float)
    gps_accuracy: Mapped[float] = mapped_column(Float)
    health_status: Mapped[HealthStatus] = mapped_column(Enum(HealthStatus, native_enum=False))
    mission_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("missions.id", name="fk_drones_mission_id", use_alter=True), nullable=True
    )
    last_seen: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    assigned_mission: Mapped[Mission | None] = relationship(
        back_populates="assigned_drone", foreign_keys=[Mission.assigned_drone_id], post_update=True
    )
    telemetry: Mapped[list[Telemetry]] = relationship(
        back_populates="drone", cascade="all, delete-orphan"
    )
    events: Mapped[list[Event]] = relationship(back_populates="drone")


class Telemetry(Base):
    __tablename__ = "telemetry"
    __table_args__ = (
        CheckConstraint(
            "battery_percentage >= 0 AND battery_percentage <= 100", name="ck_telemetry_battery"
        ),
        Index("ix_telemetry_drone_timestamp", "drone_id", "timestamp"),
    )
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    drone_id: Mapped[UUID] = mapped_column(ForeignKey("drones.id"), index=True)
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), index=True, server_default=func.now()
    )
    latitude: Mapped[float] = mapped_column(Float)
    longitude: Mapped[float] = mapped_column(Float)
    altitude: Mapped[float] = mapped_column(Float)
    speed: Mapped[float] = mapped_column(Float)
    battery_percentage: Mapped[float] = mapped_column(Float)
    temperature: Mapped[float] = mapped_column(Float)
    gps_accuracy: Mapped[float] = mapped_column(Float)
    health_status: Mapped[HealthStatus] = mapped_column(Enum(HealthStatus, native_enum=False))
    drone: Mapped[Drone] = relationship(back_populates="telemetry")


class Event(Base, TimestampMixin):
    __tablename__ = "events"
    __table_args__ = (
        CheckConstraint("confidence >= 0 AND confidence <= 1", name="ck_event_confidence"),
    )
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    event_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    drone_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("drones.id"), nullable=True, index=True
    )
    mission_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("missions.id"), nullable=True, index=True
    )
    event_type: Mapped[EventType] = mapped_column(Enum(EventType, native_enum=False))
    severity: Mapped[Severity] = mapped_column(Enum(Priority, native_enum=False))
    confidence: Mapped[float] = mapped_column(Float)
    latitude: Mapped[float | None] = mapped_column(Float)
    longitude: Mapped[float | None] = mapped_column(Float)
    description: Mapped[str] = mapped_column(Text)
    metadata_: Mapped[dict[str, Any]] = mapped_column("metadata", JsonType, default=dict)
    drone: Mapped[Drone | None] = relationship(back_populates="events")
    mission: Mapped[Mission | None] = relationship(back_populates="events")


class Approval(Base, TimestampMixin):
    __tablename__ = "approvals"
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    mission_id: Mapped[UUID | None] = mapped_column(ForeignKey("missions.id"))
    status: Mapped[str] = mapped_column(String(32), default="PENDING")
    tool_name: Mapped[str | None] = mapped_column(String(128))
    payload: Mapped[dict[str, Any]] = mapped_column(JsonType, default=dict)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class AgentRun(Base, TimestampMixin):
    __tablename__ = "agent_runs"
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    run_id: Mapped[str] = mapped_column(String(64), unique=True)
    status: Mapped[str] = mapped_column(String(32))
    execution_status: Mapped[str] = mapped_column(String(32), default="PLANNED")
    final_decision: Mapped[str | None] = mapped_column(String(64))
    error: Mapped[str | None] = mapped_column(Text)
    payload: Mapped[dict[str, Any]] = mapped_column(JsonType, default=dict)


class AgentMessage(Base, TimestampMixin):
    __tablename__ = "agent_messages"
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    agent_run_id: Mapped[UUID | None] = mapped_column(ForeignKey("agent_runs.id"))
    content: Mapped[str] = mapped_column(Text)


class ToolExecution(Base, TimestampMixin):
    __tablename__ = "tool_executions"
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    tool_name: Mapped[str] = mapped_column(String(128))
    status: Mapped[str] = mapped_column(String(32))
    run_id: Mapped[UUID | None] = mapped_column(ForeignKey("agent_runs.id"))
    payload: Mapped[dict[str, Any]] = mapped_column(JsonType, default=dict)


class Document(Base, TimestampMixin):
    __tablename__ = "documents"
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    title: Mapped[str] = mapped_column(String(256))
    content: Mapped[str] = mapped_column(Text)
    source: Mapped[str] = mapped_column(String(512), default="local")
    external_reference: Mapped[str | None] = mapped_column(String(512))
    content_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    metadata_: Mapped[dict[str, Any]] = mapped_column("metadata", JsonType, default=dict)
    chunks: Mapped[list[DocumentChunk]] = relationship(
        back_populates="document", cascade="all, delete-orphan"
    )


class DocumentChunk(Base, TimestampMixin):
    __tablename__ = "document_chunks"
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    document_id: Mapped[UUID] = mapped_column(ForeignKey("documents.id"))
    chunk_index: Mapped[int] = mapped_column()
    content: Mapped[str] = mapped_column(Text)
    metadata_: Mapped[dict[str, Any]] = mapped_column("metadata", JsonType, default=dict)
    embedding: Mapped[list[float]] = mapped_column(
        Vector(8).with_variant(JSON(), "sqlite"), nullable=False
    )
    embedding_model: Mapped[str] = mapped_column(String(128))
    document: Mapped[Document] = relationship(back_populates="chunks")

    __table_args__ = (Index("ix_document_chunks_document_chunk", "document_id", "chunk_index"),)


class MemoryType(StrEnum):
    MISSION_OUTCOME = "MISSION_OUTCOME"
    OPERATIONAL_PATTERN = "OPERATIONAL_PATTERN"
    INCIDENT_PATTERN = "INCIDENT_PATTERN"
    DECISION_OUTCOME = "DECISION_OUTCOME"
    TOOL_OUTCOME = "TOOL_OUTCOME"
    SAFETY_RELEVANT_CONTEXT = "SAFETY_RELEVANT_CONTEXT"
    USER_PREFERENCE = "USER_PREFERENCE"
    SYSTEM_OBSERVATION = "SYSTEM_OBSERVATION"


class MemoryScope(StrEnum):
    RUN = "RUN"
    MISSION = "MISSION"
    FLEET = "FLEET"
    GLOBAL = "GLOBAL"


class MemoryStatus(StrEnum):
    ACTIVE = "ACTIVE"
    ARCHIVED = "ARCHIVED"
    EXPIRED = "EXPIRED"
    INVALIDATED = "INVALIDATED"


class MemorySourceType(StrEnum):
    AGENT_RUN = "AGENT_RUN"
    MISSION = "MISSION"
    EVENT = "EVENT"
    TOOL_EXECUTION = "TOOL_EXECUTION"
    APPROVAL = "APPROVAL"
    HUMAN_INPUT = "HUMAN_INPUT"
    SYSTEM_OBSERVATION = "SYSTEM_OBSERVATION"


class MemoryRecord(Base, TimestampMixin):
    __tablename__ = "memory_records"
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    drone_id: Mapped[UUID | None] = mapped_column(ForeignKey("drones.id"))
    content: Mapped[str] = mapped_column(Text)
    memory_type: Mapped[MemoryType] = mapped_column(Enum(MemoryType))
    scope: Mapped[MemoryScope] = mapped_column(Enum(MemoryScope))
    mission_id: Mapped[UUID | None] = mapped_column(ForeignKey("missions.id"))
    agent_run_id: Mapped[UUID | None] = mapped_column(ForeignKey("agent_runs.id"))
    structured_data: Mapped[dict[str, Any]] = mapped_column(JsonType, default=dict)
    source: Mapped[str] = mapped_column(String(128))
    source_type: Mapped[MemorySourceType] = mapped_column(Enum(MemorySourceType))
    source_id: Mapped[str] = mapped_column(String(128))
    confidence: Mapped[float] = mapped_column(Float)
    importance: Mapped[float] = mapped_column(Float)
    status: Mapped[MemoryStatus] = mapped_column(Enum(MemoryStatus), default=MemoryStatus.ACTIVE)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    content_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    embedding: Mapped[list[float]] = mapped_column(
        Vector(8).with_variant(JSON(), "sqlite"), nullable=False
    )
    embedding_model: Mapped[str] = mapped_column(String(128))

    __table_args__ = (
        CheckConstraint("confidence >= 0 AND confidence <= 1", name="ck_memory_confidence"),
        CheckConstraint("importance >= 0 AND importance <= 1", name="ck_memory_importance"),
        Index("ix_memory_records_scope_status", "scope", "status"),
        Index("ix_memory_records_mission_status", "mission_id", "status"),
    )


class SafetyDecision(Base, TimestampMixin):
    __tablename__ = "safety_decisions"
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    mission_id: Mapped[UUID | None] = mapped_column(ForeignKey("missions.id"))
    decision: Mapped[str] = mapped_column(String(32))
