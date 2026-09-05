from aeromind.schemas.agents import (
    DecisionFactors,
    DecisionResult,
    EvidenceAssessment,
    RecommendedAction,
)


class DecisionAgent:
    def run(self, state: dict) -> dict:
        risk = state["risk_assessment"]
        perception = state["perception_result"]
        knowledge = state["knowledge_result"]
        evidence = state.get("evidence_assessment") or EvidenceAssessment()
        if risk.requires_human_approval:
            decision = RecommendedAction.REQUEST_HUMAN_APPROVAL
            action_source = "risk_human_approval"
        elif knowledge.relevant or perception.restricted_zone:
            decision = RecommendedAction.RAISE_ALERT
            action_source = "knowledge_or_restricted_zone"
        else:
            decision = risk.recommended_action
            action_source = "risk_recommended_action"
        factors = DecisionFactors(
            risk_level=risk.risk_level,
            risk_score=risk.risk_score,
            perception_confidence=perception.confidence,
            restricted_zone=perception.restricted_zone,
            requires_investigation=perception.requires_investigation,
            knowledge_relevant=knowledge.relevant,
            knowledge_confidence=knowledge.confidence,
            evidence_strength=evidence.evidence_strength,
            conflicting_evidence=evidence.conflicting_evidence,
            human_approval_required=risk.requires_human_approval,
            recommended_action_source=action_source,
        )
        return {
            "decision": DecisionResult(
                decision=decision,
                confidence=min(
                    0.95,
                    max(0.0, 0.5 + perception.confidence / 2 + evidence.evidence_strength * 0.05),
                ),
                actions=[decision.value],
                requires_approval=decision == RecommendedAction.REQUEST_HUMAN_APPROVAL,
                reason_summary=(
                    "Recommendation combines perception, risk, and policy; "
                    f"{evidence.memory_count} prior memory records were contextual evidence only. "
                    f"{evidence.evidence_summary}"
                ),
                evidence_assessment=evidence,
                decision_factors=factors,
            ),
            "tool_candidates": [],
            "execution_status": "COMPLETED",
        }
