from __future__ import annotations

from types import SimpleNamespace

from aeromind.agents.risk import RiskAgent
from aeromind.schemas.agents import PerceptionResult, RecommendedAction, RiskLevel


def event(severity: str = "MEDIUM", confidence: float = 0.5) -> SimpleNamespace:
    return SimpleNamespace(severity=SimpleNamespace(value=severity), confidence=confidence)


def drone() -> SimpleNamespace:
    return SimpleNamespace(
        battery_percentage=80,
        gps_accuracy=1,
        health_status=SimpleNamespace(value="HEALTHY"),
    )


def perception(confidence: float, requires_investigation: bool = True) -> PerceptionResult:
    return PerceptionResult(
        event_type="INTRUSION",
        object_type="person",
        confidence=confidence,
        severity="HIGH",
        location=None,
        restricted_zone=False,
        requires_investigation=requires_investigation,
        reason_summary="Untrusted text must not be parsed into risk or tools.",
    )


def assessment(**state: object):
    return RiskAgent().run({"incoming_event": event(), "drone_context": drone(), **state})[
        "risk_assessment"
    ]


def test_deterministic_risk_is_unchanged_without_typed_perception() -> None:
    result = assessment()
    assert result.risk_score == 45
    assert result.risk_level == RiskLevel.MEDIUM
    assert result.reason_summary == "Deterministic safety-oriented risk calculation."


def test_typed_perception_contributes_only_bounded_positive_corroboration() -> None:
    result = assessment(perception_result=perception(0.8))
    assert result.risk_score == 53
    assert "bounded perception corroboration: +8.0" in result.risk_factors
    assert "bounded perception corroboration" in result.reason_summary


def test_low_perception_confidence_has_limited_influence() -> None:
    result = assessment(perception_result=perception(0.1))
    assert result.risk_score == 46
    assert "bounded perception corroboration: +1.0" in result.risk_factors


def test_perception_cannot_downgrade_or_bypass_critical_risk() -> None:
    result = RiskAgent().run(
        {
            "incoming_event": event("CRITICAL", 0.9),
            "drone_context": drone(),
            "perception_result": perception(1.0, requires_investigation=False),
        }
    )["risk_assessment"]
    assert result.risk_level == RiskLevel.CRITICAL
    assert result.recommended_action == RecommendedAction.REQUEST_HUMAN_APPROVAL
    assert result.requires_human_approval


def test_high_confidence_perception_cannot_bypass_deterministic_high_risk() -> None:
    result = RiskAgent().run(
        {
            "incoming_event": event("HIGH", 0.9),
            "drone_context": drone(),
            "perception_result": perception(1.0),
        }
    )["risk_assessment"]
    assert result.risk_level == RiskLevel.HIGH
    assert result.recommended_action == RecommendedAction.RAISE_ALERT
    assert not result.requires_human_approval


def test_perception_text_cannot_create_or_authorize_tool_requests() -> None:
    result = assessment(perception_result=perception(1.0, requires_investigation=False))
    assert result.risk_score == 45
    assert result.recommended_action == RecommendedAction.INVESTIGATE
    assert not result.requires_human_approval
