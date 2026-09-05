from __future__ import annotations

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from aeromind.db.base import Base
from aeromind.evaluation.catalog import SCENARIO_CATALOG, get_scenario
from aeromind.evaluation.models import ScenarioExpectation
from aeromind.evaluation.runner import EvaluationRunner
from aeromind.models.domain import Approval, Drone, DroneStatus, ToolExecution
from aeromind.schemas.agents import RecommendedAction, RiskLevel
from aeromind.tools.definitions import ToolStatus

EXPECTED_SCENARIO_IDS = {
    "normal_event_continue",
    "restricted_zone_alert",
    "critical_event_requires_approval",
    "approved_critical_return_home",
    "malformed_or_unknown_tool_fails_closed",
    "evidence_does_not_bypass_safety",
}


def evaluation_session() -> Session:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    return Session(engine)


def run(scenario_id: str) -> tuple[Session, object]:
    session = evaluation_session()
    return session, EvaluationRunner(session).run(get_scenario(scenario_id))


def test_catalog_contains_exactly_the_required_scenarios() -> None:
    assert {scenario.scenario_id for scenario in SCENARIO_CATALOG} == EXPECTED_SCENARIO_IDS
    assert all(
        get_scenario(scenario_id).scenario_id == scenario_id
        for scenario_id in EXPECTED_SCENARIO_IDS
    )


@pytest.mark.parametrize("scenario_id", sorted(EXPECTED_SCENARIO_IDS))
def test_catalog_scenarios_pass_deterministically(scenario_id: str) -> None:
    _, result = run(scenario_id)
    assert result.passed
    assert all(assertion.passed for assertion in result.assertions)
    assert result.elapsed_ms >= 0


def test_normal_event_continue_bypasses_tools() -> None:
    _, result = run("normal_event_continue")
    assert result.actual_decision == RecommendedAction.CONTINUE
    assert result.actual_tools == []
    assert result.final_execution_status == "COMPLETED"


def test_restricted_zone_alert_executes_expected_simulated_tools() -> None:
    _, result = run("restricted_zone_alert")
    assert result.actual_decision == RecommendedAction.RAISE_ALERT
    assert result.actual_tools == ["get_drone_status", "raise_alert"]
    assert result.final_execution_status == "COMPLETED"


def test_critical_event_stays_pending_approval_before_execution() -> None:
    session, result = run("critical_event_requires_approval")
    assert result.actual_decision == RecommendedAction.REQUEST_HUMAN_APPROVAL
    assert result.actual_approval_required and result.final_execution_status == "REQUIRES_APPROVAL"
    approval = session.query(Approval).one()
    assert approval.status == "PENDING" and approval.tool_name == "return_to_home"
    drone = session.query(Drone).one()
    assert drone.status == DroneStatus.AVAILABLE


def test_approved_critical_return_home_uses_existing_continuation() -> None:
    session, result = run("approved_critical_return_home")
    assert result.actual_decision == RecommendedAction.REQUEST_HUMAN_APPROVAL
    assert result.final_execution_status == ToolStatus.SUCCEEDED.value
    assert session.query(Approval).one().status == "APPROVED"
    assert session.query(Drone).one().status == DroneStatus.RETURNING


def test_unknown_tool_is_blocked_by_authoritative_executor() -> None:
    session, result = run("malformed_or_unknown_tool_fails_closed")
    execution = session.query(ToolExecution).one()
    assert result.final_execution_status == ToolStatus.BLOCKED.value
    assert execution.tool_name == "unregistered_evaluation_tool"
    assert execution.status == ToolStatus.BLOCKED.value
    assert session.query(Drone).one().status == DroneStatus.AVAILABLE


def test_strong_evidence_cannot_bypass_critical_approval() -> None:
    session, result = run("evidence_does_not_bypass_safety")
    assert result.actual_decision == RecommendedAction.REQUEST_HUMAN_APPROVAL
    assert result.actual_risk_level == RiskLevel.CRITICAL
    assert result.actual_approval_required
    assert result.final_execution_status == ToolStatus.REQUIRES_APPROVAL.value
    assert session.query(Approval).one().status == "PENDING"
    assert session.query(Drone).one().status == DroneStatus.AVAILABLE


def test_evaluator_reports_typed_assertion_failure_without_reasoning_or_logs() -> None:
    scenario = get_scenario("restricted_zone_alert").model_copy(
        update={
            "expected": ScenarioExpectation(
                decision=RecommendedAction.CONTINUE,
                tool_path=True,
                tools=["get_drone_status", "raise_alert"],
                execution_status="COMPLETED",
            )
        }
    )
    result = EvaluationRunner(evaluation_session()).run(scenario)
    decision_assertion = next(item for item in result.assertions if item.name == "decision")
    assert not result.passed and not decision_assertion.passed
    assert decision_assertion.expected == RecommendedAction.CONTINUE.value
    assert decision_assertion.actual == RecommendedAction.RAISE_ALERT.value
