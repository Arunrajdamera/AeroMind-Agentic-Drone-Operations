from __future__ import annotations

from uuid import uuid4

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

import aeromind.graph.workflow as workflow_module
from aeromind.graph.workflow import build_workflow, route_after_decision
from aeromind.models.domain import (
    Approval,
    Drone,
    DroneStatus,
    Event,
    EventType,
    HealthStatus,
    Mission,
    MissionStatus,
    MissionType,
    Priority,
)
from aeromind.schemas.agents import DecisionResult, RecommendedAction


def decision(action: RecommendedAction) -> DecisionResult:
    return DecisionResult(
        decision=action,
        confidence=0.7,
        actions=[action.value],
        requires_approval=action == RecommendedAction.REQUEST_HUMAN_APPROVAL,
        reason_summary="Typed test decision.",
    )


def test_router_is_deterministic_and_uses_only_typed_tool_producing_decisions() -> None:
    for action in (
        RecommendedAction.INVESTIGATE,
        RecommendedAction.RAISE_ALERT,
        RecommendedAction.REQUEST_HUMAN_APPROVAL,
        RecommendedAction.RETURN_TO_HOME,
    ):
        assert route_after_decision({"decision": decision(action)}) == "tool_path"
    for action in (RecommendedAction.CONTINUE, RecommendedAction.ABORT_MISSION):
        assert route_after_decision({"decision": decision(action)}) == "no_tool_path"
    assert route_after_decision({}) == "no_tool_path"


def test_continue_bypasses_tool_path_without_creating_tool_state() -> None:
    state = {"decision": decision(RecommendedAction.CONTINUE), "tool_candidates": []}
    assert route_after_decision(state) == "no_tool_path"
    assert state["tool_candidates"] == []
    assert "tool_requests" not in state and "tool_results" not in state


def test_compiled_workflow_continue_bypasses_planner_and_executor(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from aeromind.db.base import Base

    class ContinueDecisionAgent:
        def run(self, state: dict) -> dict:
            del state
            return {
                "decision": decision(RecommendedAction.CONTINUE),
                "tool_candidates": [],
                "execution_status": "COMPLETED",
            }

    class FailingToolPlanner:
        def run(self, state: dict) -> dict:
            del state
            raise AssertionError("ToolPlanner must not run for CONTINUE")

    class FailingGraphToolExecutor:
        def __init__(self, session: Session) -> None:
            del session

        def run(self, state: dict) -> dict:
            del state
            raise AssertionError("GraphToolExecutor must not run for CONTINUE")

    class RecordingMemoryAgent:
        calls = 0

        def __init__(self, service: object) -> None:
            del service

        def run(self, state: dict) -> dict:
            del state
            type(self).calls += 1
            return {"recorded_memory_ids": []}

    monkeypatch.setattr(workflow_module, "DecisionAgent", ContinueDecisionAgent)
    monkeypatch.setattr(workflow_module, "ToolPlanner", FailingToolPlanner)
    monkeypatch.setattr(workflow_module, "GraphToolExecutor", FailingGraphToolExecutor)
    monkeypatch.setattr(workflow_module, "MemoryRecordingAgent", RecordingMemoryAgent)
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    session = Session(engine)
    drone = Drone(
        drone_id="DR-ROUTING-CONTINUE",
        name="Continue routing simulation drone",
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
    event = Event(
        event_id="ROUTING-CONTINUE",
        drone_id=drone.id,
        event_type=EventType.BATTERY_WARNING,
        severity=Priority.LOW,
        confidence=0.5,
        description="Simulated no-tool routing event",
        metadata_={"simulated": True},
    )
    session.add(event)
    session.commit()

    result = dict(
        workflow_module.build_workflow(session).invoke(
            {
                "request_id": str(uuid4()),
                "run_id": str(uuid4()),
                "incoming_event": event,
                "drone_context": drone,
                "execute_tools": True,
            }
        )
    )
    assert result["decision"].decision == RecommendedAction.CONTINUE
    assert result["execution_status"] == "COMPLETED"
    assert result["recorded_memory_ids"] == [] and RecordingMemoryAgent.calls == 1
    assert result["tool_candidates"] == []
    assert "tool_requests" not in result and "tool_results" not in result


def test_compiled_workflow_routes_raise_alert_through_existing_tool_path() -> None:
    from aeromind.db.base import Base

    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    session = Session(engine)
    mission = Mission(
        mission_id="ROUTING-MISSION",
        mission_type=MissionType.PERIMETER_INSPECTION,
        priority=Priority.HIGH,
        target_latitude=1,
        target_longitude=1,
        objective="Simulated routing test",
        status=MissionStatus.PLANNED,
    )
    drone = Drone(
        drone_id="DR-ROUTING",
        name="Routing simulation drone",
        status=DroneStatus.AVAILABLE,
        latitude=1,
        longitude=1,
        battery_percentage=80,
        temperature=20,
        gps_accuracy=1,
        health_status=HealthStatus.HEALTHY,
    )
    session.add_all([mission, drone])
    session.flush()
    event = Event(
        event_id="ROUTING-ALERT",
        mission_id=mission.id,
        drone_id=drone.id,
        event_type=EventType.INTRUSION,
        severity=Priority.HIGH,
        confidence=0.9,
        description="Simulated restricted-zone event",
        metadata_={"restricted_zone": True, "simulated": True},
    )
    session.add(event)
    session.commit()

    result = dict(
        build_workflow(session).invoke(
            {
                "request_id": str(uuid4()),
                "run_id": str(uuid4()),
                "incoming_event": event,
                "mission_context": mission,
                "drone_context": drone,
                "execute_tools": False,
            }
        )
    )
    assert result["decision"].decision == RecommendedAction.RAISE_ALERT
    assert [call.name for call in result["tool_requests"]] == ["get_drone_status", "raise_alert"]
    assert result["tool_results"] == [] and result["execution_status"] == "PLANNED"


def test_compiled_workflow_routes_human_approval_to_existing_approval_gate() -> None:
    from aeromind.db.base import Base

    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    session = Session(engine)
    drone = Drone(
        drone_id="DR-ROUTING-CRITICAL",
        name="Critical routing simulation drone",
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
    event = Event(
        event_id="ROUTING-CRITICAL",
        drone_id=drone.id,
        event_type=EventType.INTRUSION,
        severity=Priority.CRITICAL,
        confidence=0.9,
        description="Simulated critical event",
        metadata_={"restricted_zone": True, "simulated": True},
    )
    session.add(event)
    session.commit()

    result = dict(
        build_workflow(session).invoke(
            {
                "request_id": str(uuid4()),
                "run_id": str(uuid4()),
                "incoming_event": event,
                "drone_context": drone,
                "execute_tools": True,
            }
        )
    )
    assert result["decision"].decision == RecommendedAction.REQUEST_HUMAN_APPROVAL
    assert [call.name for call in result["tool_requests"]] == ["return_to_home"]
    assert result["tool_results"][0].status.value == "REQUIRES_APPROVAL"
    approval = session.query(Approval).one()
    assert approval.status == "PENDING" and approval.tool_name == "return_to_home"
