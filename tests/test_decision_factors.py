from __future__ import annotations

from aeromind.agents.decision import DecisionAgent
from aeromind.schemas.agents import (
    EvidenceAssessment,
    KnowledgeResult,
    PerceptionResult,
    RecommendedAction,
    RiskAssessment,
    RiskLevel,
)


def state(*, critical: bool = False, knowledge_relevant: bool = False) -> dict:
    return {
        "risk_assessment": RiskAssessment(
            risk_level=RiskLevel.CRITICAL if critical else RiskLevel.MEDIUM,
            risk_score=91 if critical else 52,
            risk_factors=["safe structured risk factor"],
            recommended_action=RecommendedAction.REQUEST_HUMAN_APPROVAL
            if critical
            else RecommendedAction.INVESTIGATE,
            requires_human_approval=critical,
            reason_summary="Not included in factors.",
        ),
        "perception_result": PerceptionResult(
            event_type="INTRUSION",
            object_type="person",
            confidence=0.76,
            severity="HIGH",
            location=None,
            restricted_zone=False,
            requires_investigation=True,
            reason_summary="Raw VLM output that must not be included in factors.",
        ),
        "knowledge_result": KnowledgeResult(
            relevant=knowledge_relevant,
            policy="Sensitive retrieved policy content must not be included in factors.",
            confidence=0.64,
            retrieved_chunks=[{"content_excerpt": "Sensitive retrieval content"}],
        ),
        "evidence_assessment": EvidenceAssessment(
            evidence_strength=0.58,
            conflicting_evidence=True,
            evidence_summary="Sensitive memory summary must not be included in factors.",
        ),
    }


def test_decision_factors_capture_only_safe_structured_metadata() -> None:
    result = DecisionAgent().run(state())["decision"]
    factors = result.decision_factors
    assert factors is not None
    assert factors.risk_level == RiskLevel.MEDIUM and factors.risk_score == 52
    assert factors.perception_confidence == 0.76 and factors.requires_investigation
    assert factors.knowledge_confidence == 0.64 and not factors.knowledge_relevant
    assert factors.evidence_strength == 0.58 and factors.conflicting_evidence
    assert factors.recommended_action_source == "risk_recommended_action"
    serialized = factors.model_dump_json()
    assert "Raw VLM output" not in serialized
    assert "Sensitive retrieved policy" not in serialized
    assert "Sensitive memory summary" not in serialized


def test_decision_factors_reflect_existing_escalation_precedence_without_tools() -> None:
    knowledge_escalation = DecisionAgent().run(state(knowledge_relevant=True))
    assert knowledge_escalation["decision"].decision == RecommendedAction.RAISE_ALERT
    assert (
        knowledge_escalation["decision"].decision_factors.recommended_action_source
        == "knowledge_or_restricted_zone"
    )
    assert knowledge_escalation["tool_candidates"] == []

    critical = DecisionAgent().run(state(critical=True))
    assert critical["decision"].decision == RecommendedAction.REQUEST_HUMAN_APPROVAL
    assert critical["decision"].requires_approval
    assert critical["decision"].decision_factors.human_approval_required
    assert critical["decision"].decision_factors.recommended_action_source == "risk_human_approval"
    assert critical["tool_candidates"] == []
