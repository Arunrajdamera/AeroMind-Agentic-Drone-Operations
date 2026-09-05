from __future__ import annotations

from uuid import uuid4

from aeromind.agents.decision import DecisionAgent
from aeromind.agents.evidence import EvidenceAssessmentAgent
from aeromind.models.domain import MemoryScope, MemorySourceType, MemoryType
from aeromind.schemas.agents import (
    KnowledgeResult,
    PerceptionResult,
    RecommendedAction,
    RiskAssessment,
    RiskLevel,
)
from aeromind.schemas.memory import MemoryEvidence


def memory(confidence: float, **structured_data: str) -> MemoryEvidence:
    return MemoryEvidence(
        memory_id=uuid4(),
        memory_type=MemoryType.INCIDENT_PATTERN,
        scope=MemoryScope.MISSION,
        content="Sensitive historical details must remain outside the evidence summary.",
        similarity_score=0.8,
        confidence=confidence,
        importance=0.8,
        source="test",
        source_type=MemorySourceType.EVENT,
        source_id="EV-1",
        structured_data=structured_data,
    )


def perception() -> PerceptionResult:
    return PerceptionResult(
        event_type="INTRUSION",
        object_type="person",
        confidence=0.8,
        severity="HIGH",
        location=None,
        restricted_zone=False,
        requires_investigation=True,
        reason_summary="Simulated perception.",
    )


def risk(critical: bool = False) -> RiskAssessment:
    return RiskAssessment(
        risk_level=RiskLevel.CRITICAL if critical else RiskLevel.LOW,
        risk_score=90 if critical else 20,
        risk_factors=["test"],
        recommended_action=(
            RecommendedAction.REQUEST_HUMAN_APPROVAL if critical else RecommendedAction.CONTINUE
        ),
        requires_human_approval=critical,
        reason_summary="Deterministic risk.",
    )


def test_evidence_assessment_handles_absent_and_strong_evidence_deterministically() -> None:
    agent = EvidenceAssessmentAgent()
    absent = agent.run(
        {"knowledge_result": KnowledgeResult(relevant=False, policy=""), "memory_context": []}
    )["evidence_assessment"]
    strong = agent.run(
        {
            "knowledge_result": KnowledgeResult(
                relevant=True,
                policy="Retrieved policy.",
                confidence=1.0,
                retrieved_chunks=[{"metadata": {}}],
            ),
            "memory_context": [memory(0.8), memory(1.0)],
        }
    )["evidence_assessment"]
    assert absent.evidence_strength == 0 and absent.memory_count == 0
    assert strong.knowledge_available and strong.memory_count == 2
    assert strong.memory_confidence == 0.9
    assert strong.evidence_strength == 0.96
    assert 0 <= strong.evidence_strength <= 1
    assert "Sensitive historical details" not in strong.evidence_summary


def test_evidence_conflicts_use_only_explicit_structured_action_metadata() -> None:
    assessment = EvidenceAssessmentAgent().run(
        {
            "knowledge_result": KnowledgeResult(
                relevant=True,
                policy="Policy text is not parsed.",
                confidence=0.6,
                retrieved_chunks=[{"metadata": {"recommended_action": "RAISE_ALERT"}}],
            ),
            "memory_context": [memory(0.8, decision="RETURN_TO_HOME")],
        }
    )["evidence_assessment"]
    assert assessment.conflicting_evidence
    assert assessment.evidence_strength == 0.68


def test_decision_consumes_evidence_without_overriding_risk_or_authorizing_tools() -> None:
    assessment = EvidenceAssessmentAgent().run(
        {
            "knowledge_result": KnowledgeResult(relevant=False, policy=""),
            "memory_context": [memory(1.0)],
        }
    )["evidence_assessment"]
    result = DecisionAgent().run(
        {
            "risk_assessment": risk(),
            "perception_result": perception(),
            "knowledge_result": KnowledgeResult(relevant=False, policy=""),
            "evidence_assessment": assessment,
        }
    )
    decision = result["decision"]
    assert decision.decision == RecommendedAction.CONTINUE
    assert decision.confidence == 0.92
    assert decision.evidence_assessment == assessment
    assert result["tool_candidates"] == []

    critical = DecisionAgent().run(
        {
            "risk_assessment": risk(critical=True),
            "perception_result": perception(),
            "knowledge_result": KnowledgeResult(relevant=False, policy=""),
            "evidence_assessment": assessment,
        }
    )["decision"]
    assert critical.decision == RecommendedAction.REQUEST_HUMAN_APPROVAL
    assert critical.requires_approval
