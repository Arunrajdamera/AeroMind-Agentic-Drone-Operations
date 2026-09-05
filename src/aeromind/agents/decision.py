from aeromind.schemas.agents import DecisionResult, RecommendedAction


class DecisionAgent:
    def run(self, state: dict) -> dict:
        risk = state["risk_assessment"]
        perception = state["perception_result"]
        knowledge = state["knowledge_result"]
        memory_context = state.get("memory_context", [])
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
                confidence=min(0.95, 0.5 + perception.confidence / 2),
                actions=[decision.value],
                requires_approval=decision == RecommendedAction.REQUEST_HUMAN_APPROVAL,
                reason_summary=(
                    "Recommendation combines perception, risk, and policy; "
                    f"{len(memory_context)} prior memory records were contextual evidence only."
                ),
            ),
            "tool_candidates": [],
            "execution_status": "COMPLETED",
        }
