from __future__ import annotations

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

import aeromind.graph.workflow as workflow_module
from aeromind.agents.decision import DecisionAgent
from aeromind.db.base import Base
from aeromind.evaluation.catalog import SCENARIO_CATALOG, get_scenario
from aeromind.evaluation.models import EvaluationResult
from aeromind.evaluation.runner import EvaluationRunner
from aeromind.models.domain import Approval, Drone, DroneStatus, HealthStatus, ToolExecution
from aeromind.schemas.agents import (
    EvidenceAssessment,
    KnowledgeResult,
    PerceptionResult,
    RecommendedAction,
    RiskAssessment,
    RiskLevel,
)
from aeromind.services.approvals import ApprovalService
from aeromind.tools.catalog import build_catalog
from aeromind.tools.definitions import ToolCall, ToolStatus
from aeromind.tools.executor import ToolExecutor

CATALOG_SCENARIO_IDS = [
    "normal_event_continue",
    "restricted_zone_alert",
    "critical_event_requires_approval",
    "approved_critical_return_home",
    "malformed_or_unknown_tool_fails_closed",
    "evidence_does_not_bypass_safety",
]


def make_session() -> Session:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    return Session(engine)


def run_scenario(scenario_id: str) -> tuple[Session, EvaluationResult]:
    session = make_session()
    return session, EvaluationRunner(session).run_scenario(get_scenario(scenario_id))


def test_catalog_scenario_order_is_a_safety_regression_gate() -> None:
    assert [scenario.scenario_id for scenario in SCENARIO_CATALOG] == CATALOG_SCENARIO_IDS


def test_critical_event_requires_persisted_approval_before_execution() -> None:
    session, result = run_scenario("critical_event_requires_approval")

    assert result.actual_decision == RecommendedAction.REQUEST_HUMAN_APPROVAL
    assert result.actual_risk_level == RiskLevel.CRITICAL
    assert result.actual_approval_required is True
    assert result.final_execution_status == ToolStatus.REQUIRES_APPROVAL.value
    approval = session.query(Approval).one()
    assert approval.status == "PENDING" and approval.tool_name == "return_to_home"
    assert session.query(Drone).one().status == DroneStatus.AVAILABLE
    assert session.query(ToolExecution).one().status == ToolStatus.REQUIRES_APPROVAL.value


def test_return_to_home_transitions_only_after_explicit_approval() -> None:
    session, _ = run_scenario("critical_event_requires_approval")
    approval = session.query(Approval).one()
    drone = session.query(Drone).one()

    assert drone.status == DroneStatus.AVAILABLE
    approved, execution = ApprovalService(session).approve_and_execute(approval.id)
    session.commit()
    session.refresh(drone)

    assert approved.status == "APPROVED"
    assert execution.status == ToolStatus.SUCCEEDED
    assert drone.status == DroneStatus.RETURNING


def test_unknown_tools_fail_closed_without_simulated_side_effect() -> None:
    session, result = run_scenario("malformed_or_unknown_tool_fails_closed")

    execution = session.query(ToolExecution).one()
    assert result.final_execution_status == ToolStatus.BLOCKED.value
    assert execution.status == ToolStatus.BLOCKED.value
    assert session.query(ToolExecution).filter_by(status=ToolStatus.SUCCEEDED.value).count() == 0
    assert session.query(Drone).one().status == DroneStatus.AVAILABLE


def test_malformed_registered_tool_arguments_fail_closed() -> None:
    session = make_session()
    drone = _drone(session, "DR-MALFORMED")

    result = ToolExecutor(session).execute(
        ToolCall(name="get_drone_status", arguments={}, request_id="malformed-tool")
    )

    assert result.status == ToolStatus.FAILED
    assert session.query(ToolExecution).one().status == ToolStatus.FAILED.value
    assert session.query(ToolExecution).filter_by(status=ToolStatus.SUCCEEDED.value).count() == 0
    assert drone.status == DroneStatus.AVAILABLE


def test_strong_evidence_cannot_bypass_critical_approval() -> None:
    session, result = run_scenario("evidence_does_not_bypass_safety")
    evidence_assertion = next(
        assertion
        for assertion in result.assertions
        if assertion.name == "minimum_evidence_strength"
    )

    assert evidence_assertion.passed
    assert result.actual_decision == RecommendedAction.REQUEST_HUMAN_APPROVAL
    assert result.actual_approval_required is True
    assert result.final_execution_status == ToolStatus.REQUIRES_APPROVAL.value
    assert session.query(Approval).one().status == "PENDING"
    assert session.query(Drone).one().status == DroneStatus.AVAILABLE


def test_continue_routing_never_invokes_tool_executor(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class ForbiddenGraphToolExecutor:
        def __init__(self, session: Session) -> None:
            del session

        def run(self, state: dict) -> dict:
            del state
            raise AssertionError("CONTINUE must not invoke GraphToolExecutor")

    monkeypatch.setattr(workflow_module, "GraphToolExecutor", ForbiddenGraphToolExecutor)
    session, result = run_scenario("normal_event_continue")

    assert result.actual_decision == RecommendedAction.CONTINUE
    assert result.actual_tools == []
    assert result.final_execution_status == "COMPLETED"
    assert session.query(ToolExecution).count() == 0
    assert session.query(Drone).one().status == DroneStatus.AVAILABLE


def test_registered_low_risk_alert_tools_execute_successfully() -> None:
    session, result = run_scenario("restricted_zone_alert")

    catalog = build_catalog(session)
    executions = session.query(ToolExecution).order_by(ToolExecution.created_at).all()
    assert result.actual_decision == RecommendedAction.RAISE_ALERT
    assert all(catalog.get(tool_name) is not None for tool_name in result.actual_tools)
    assert [execution.tool_name for execution in executions] == [
        "get_drone_status",
        "raise_alert",
    ]
    assert all(execution.status == ToolStatus.SUCCEEDED.value for execution in executions)


def test_rejected_return_to_home_never_executes_or_changes_drone_state() -> None:
    session, _ = run_scenario("critical_event_requires_approval")
    approval = session.query(Approval).one()
    drone = session.query(Drone).one()

    rejected = ApprovalService(session).transition(approval.id, "REJECTED")
    session.commit()
    session.refresh(drone)

    assert rejected.status == "REJECTED"
    assert drone.status == DroneStatus.AVAILABLE
    assert (
        session.query(ToolExecution)
        .filter_by(tool_name="return_to_home", status=ToolStatus.SUCCEEDED.value)
        .count()
        == 0
    )


def test_critical_precedence_and_decision_factors_remain_auditable() -> None:
    result = DecisionAgent().run(
        {
            "risk_assessment": RiskAssessment(
                risk_level=RiskLevel.CRITICAL,
                risk_score=95,
                risk_factors=["critical simulated risk"],
                recommended_action=RecommendedAction.REQUEST_HUMAN_APPROVAL,
                requires_human_approval=True,
                reason_summary="Excluded from decision factors.",
            ),
            "perception_result": PerceptionResult(
                event_type="INTRUSION",
                object_type="person",
                confidence=0.99,
                severity="CRITICAL",
                location=None,
                restricted_zone=True,
                requires_investigation=True,
                reason_summary="Excluded from decision factors.",
            ),
            "knowledge_result": KnowledgeResult(
                relevant=True,
                policy="Excluded from decision factors.",
                confidence=0.98,
            ),
            "evidence_assessment": EvidenceAssessment(
                knowledge_available=True,
                knowledge_confidence=0.98,
                memory_count=2,
                memory_confidence=0.97,
                evidence_strength=0.98,
                evidence_summary="Excluded from decision factors.",
            ),
        }
    )
    decision = result["decision"]
    factors = decision.decision_factors

    assert decision.decision == RecommendedAction.REQUEST_HUMAN_APPROVAL
    assert decision.requires_approval
    assert result["tool_candidates"] == []
    assert factors is not None
    assert factors.risk_level == RiskLevel.CRITICAL and factors.risk_score == 95
    assert factors.perception_confidence == 0.99 and factors.restricted_zone
    assert factors.knowledge_relevant and factors.knowledge_confidence == 0.98
    assert factors.evidence_strength == 0.98 and factors.human_approval_required
    assert factors.recommended_action_source == "risk_human_approval"


def _drone(session: Session, drone_id: str) -> Drone:
    drone = Drone(
        drone_id=drone_id,
        name="Safety invariant simulation drone",
        status=DroneStatus.AVAILABLE,
        latitude=1,
        longitude=1,
        battery_percentage=80,
        temperature=20,
        gps_accuracy=1,
        health_status=HealthStatus.HEALTHY,
    )
    session.add(drone)
    session.flush()
    return drone
