from aeromind.schemas.agents import RecommendedAction, RiskAssessment, RiskLevel


class RiskAgent:
    def run(self, state: dict) -> dict:
        event, drone = state["incoming_event"], state.get("drone_context")
        score = {"LOW": 20, "MEDIUM": 40, "HIGH": 65, "CRITICAL": 85}[
            event.severity.value
        ] + event.confidence * 10
        factors = [f"event severity: {event.severity.value}"]
        if drone is None:
            score += 20
            factors.append("no eligible drone")
        else:
            if drone.battery_percentage < 25:
                score += 25
                factors.append("low battery")
            if drone.gps_accuracy > 15:
                score += 15
                factors.append("GPS degraded")
            if drone.health_status.value != "HEALTHY":
                score += 20
                factors.append("drone health degraded")
        score = min(100, score)
        level = (
            RiskLevel.CRITICAL
            if score >= 85
            else RiskLevel.HIGH
            if score >= 65
            else RiskLevel.MEDIUM
            if score >= 40
            else RiskLevel.LOW
        )
        action = (
            RecommendedAction.REQUEST_HUMAN_APPROVAL
            if level == RiskLevel.CRITICAL
            else RecommendedAction.RAISE_ALERT
            if level == RiskLevel.HIGH
            else RecommendedAction.INVESTIGATE
        )
        return {
            "risk_assessment": RiskAssessment(
                risk_level=level,
                risk_score=score,
                risk_factors=factors,
                recommended_action=action,
                requires_human_approval=level == RiskLevel.CRITICAL,
                reason_summary="Deterministic safety-oriented risk calculation.",
            )
        }
