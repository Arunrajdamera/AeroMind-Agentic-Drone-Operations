from aeromind.schemas.agents import DecisionResult, EvidenceAssessment, RecommendedAction


class DecisionAgent:
    def run(self, state: dict) -> dict:
        risk = state["risk_assessment"]
        perception = state["perception_result"]
        knowledge = state["knowledge_result"]
        evidence = state.get("evidence_assessment") or EvidenceAssessment()
        decision = (
            RecommendedAction.REQUEST_HUMAN_APPROVAL
            if risk.requires_human_approval
            else RecommendedAction.RAISE_ALERT
            if knowledge.relevant or perception.restricted_zone
            else risk.recommended_action
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
            ),
            "tool_candidates": [],
            "execution_status": "COMPLETED",
        }
