from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import Field

from aeromind.schemas.common import DomainModel


class RiskLevel(StrEnum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class RecommendedAction(StrEnum):
    CONTINUE = "CONTINUE"
    INVESTIGATE = "INVESTIGATE"
    RETURN_TO_HOME = "RETURN_TO_HOME"
    ABORT_MISSION = "ABORT_MISSION"
    RAISE_ALERT = "RAISE_ALERT"
    REQUEST_HUMAN_APPROVAL = "REQUEST_HUMAN_APPROVAL"


class MissionPlan(DomainModel):
    selected_drone_id: str | None
    objective: str
    mission_type: str
    priority: str
    planned_action: RecommendedAction
    constraints: list[str] = Field(default_factory=list)
    reason_summary: str


class PerceptionResult(DomainModel):
    event_type: str
    object_type: str
    confidence: float = Field(ge=0, le=1)
    severity: str
    location: str | None
    restricted_zone: bool
    requires_investigation: bool
    reason_summary: str


class RiskAssessment(DomainModel):
    risk_level: RiskLevel
    risk_score: float = Field(ge=0, le=100)
    risk_factors: list[str]
    recommended_action: RecommendedAction
    requires_human_approval: bool
    reason_summary: str


class KnowledgeResult(DomainModel):
    relevant: bool
    policy: str
    sources: list[str] = Field(default_factory=list)
    confidence: float = Field(default=0.0, ge=0, le=1)
    retrieved_chunks: list[dict[str, Any]] = Field(default_factory=list)


class EvidenceAssessment(DomainModel):
    """Safe, deterministic metadata about retrieved knowledge and memory evidence."""

    knowledge_available: bool = False
    knowledge_confidence: float = Field(default=0.0, ge=0, le=1)
    memory_count: int = Field(default=0, ge=0)
    memory_confidence: float = Field(default=0.0, ge=0, le=1)
    evidence_strength: float = Field(default=0.0, ge=0, le=1)
    conflicting_evidence: bool = False
    evidence_summary: str = Field(
        default="No retrieved operational evidence is available.", max_length=500
    )


class DecisionResult(DomainModel):
    decision: RecommendedAction
    confidence: float = Field(ge=0, le=1)
    actions: list[str]
    requires_approval: bool
    reason_summary: str
    evidence_assessment: EvidenceAssessment | None = None
