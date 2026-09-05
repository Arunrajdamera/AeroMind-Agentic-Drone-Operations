from __future__ import annotations

import logging
from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from aeromind.core.logging import JsonFormatter
from aeromind.graph.workflow import build_workflow, instrument_agent_node
from aeromind.models.domain import (
    AgentRun,
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
from aeromind.schemas.agents import PerceptionResult
from aeromind.tools.definitions import ToolCall


def agent_node_events(caplog: pytest.LogCaptureFixture) -> list[logging.LogRecord]:
    return [
        record
        for record in caplog.records
        if record.name == "aeromind.graph.workflow" and record.getMessage() == "agent.node"
    ]


def test_compiled_workflow_emits_safe_ordered_node_telemetry(
    caplog: pytest.LogCaptureFixture,
) -> None:
    from aeromind.db.base import Base

    caplog.set_level(logging.INFO, logger="aeromind.graph.workflow")
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    session = Session(engine)
    mission = Mission(
        mission_id="OBSERVE-MISSION",
        mission_type=MissionType.PERIMETER_INSPECTION,
        priority=Priority.HIGH,
        target_latitude=1,
        target_longitude=1,
        objective="Simulated observability test",
        status=MissionStatus.PLANNED,
    )
    drone = Drone(
        drone_id="DR-OBSERVE",
        name="Observability simulation drone",
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
        event_id="OBSERVE-EVENT",
        mission_id=mission.id,
        drone_id=drone.id,
        event_type=EventType.INTRUSION,
        severity=Priority.HIGH,
        confidence=0.9,
        description="PROMPT-AND-MEMORY-CONTENT-DO-NOT-LOG",
        metadata_={"restricted_zone": True, "simulated": True},
    )
    run_id = "observe-run"
    agent_run = AgentRun(run_id=run_id, status="RUNNING")
    session.add_all([event, agent_run])
    session.commit()

    result = dict(
        build_workflow(session).invoke(
            {
                "request_id": "observe-request",
                "run_id": run_id,
                "agent_run_id": agent_run.id,
                "mission_id": mission.mission_id,
                "drone_id": drone.drone_id,
                "incoming_event": event,
                "mission_context": mission,
                "drone_context": drone,
                "execute_tools": False,
            }
        )
    )
    assert result["execution_status"] == "PLANNED"
    events = agent_node_events(caplog)
    expected_nodes = [
        "mission_planner",
        "perception",
        "risk",
        "knowledge",
        "memory_retrieval",
        "evidence_assessment",
        "decision",
        "tool_planner",
        "tool_executor",
        "memory_recording",
    ]
    assert [(record.node_name, record.status) for record in events] == [
        pair for node in expected_nodes for pair in ((node, "STARTED"), (node, "COMPLETED"))
    ]
    completed = [record for record in events if record.status == "COMPLETED"]
    assert all(record.duration_ms >= 0 for record in completed)
    assert all(
        record.request_id == "observe-request" and record.run_id == run_id for record in events
    )
    assert all(record.agent_run_id == str(agent_run.id) for record in events)
    assert all(
        record.mission_id == mission.mission_id and record.drone_id == drone.drone_id
        for record in events
    )
    rendered = "\n".join(JsonFormatter().format(record) for record in events)
    assert "PROMPT-AND-MEMORY-CONTENT-DO-NOT-LOG" not in rendered
    assert "arguments" not in rendered


def test_node_telemetry_excludes_content_descriptions_and_tool_arguments(
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.INFO, logger="aeromind.graph.workflow")
    state = {"request_id": "request", "run_id": "run"}
    perception = PerceptionResult(
        event_type="INTRUSION",
        object_type="person",
        confidence=0.7,
        severity="HIGH",
        location=None,
        restricted_zone=True,
        requires_investigation=True,
        reason_summary="VLM-DESCRIPTION-DO-NOT-LOG",
    )
    instrument_agent_node("perception", lambda _state: {"perception_result": perception})(state)
    instrument_agent_node(
        "memory_retrieval",
        lambda _state: {"memory_context": [SimpleNamespace(content="MEMORY-CONTENT-DO-NOT-LOG")]},
    )(state)
    instrument_agent_node(
        "tool_planner",
        lambda _state: {
            "tool_candidates": ["raise_alert"],
            "tool_requests": [
                ToolCall(
                    name="raise_alert",
                    arguments={"description": "TOOL-ARGUMENT-DO-NOT-LOG"},
                    request_id="request",
                )
            ],
        },
    )(state)
    rendered = "\n".join(JsonFormatter().format(record) for record in agent_node_events(caplog))
    assert "VLM-DESCRIPTION-DO-NOT-LOG" not in rendered
    assert "MEMORY-CONTENT-DO-NOT-LOG" not in rendered
    assert "TOOL-ARGUMENT-DO-NOT-LOG" not in rendered


def test_failed_node_emits_safe_failed_telemetry(caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.INFO, logger="aeromind.graph.workflow")

    def fail(_state: dict) -> dict:
        raise RuntimeError("SENSITIVE-PROVIDER-DETAIL-DO-NOT-LOG")

    with pytest.raises(RuntimeError):
        instrument_agent_node("risk", fail)({"request_id": "request", "run_id": "run"})
    events = agent_node_events(caplog)
    assert [(record.node_name, record.status) for record in events] == [
        ("risk", "STARTED"),
        ("risk", "FAILED"),
    ]
    assert events[-1].duration_ms >= 0 and events[-1].error_type == "RuntimeError"
    assert "SENSITIVE-PROVIDER-DETAIL-DO-NOT-LOG" not in JsonFormatter().format(events[-1])
