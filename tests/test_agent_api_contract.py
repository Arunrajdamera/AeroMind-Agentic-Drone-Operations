from __future__ import annotations

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from aeromind.api.routes.agents import get_session
from aeromind.api.routes.simulation import get_session as simulation_get_session
from aeromind.db.base import Base
from aeromind.main import create_app
from aeromind.models.domain import (
    AgentRun,
    Approval,
    Drone,
    DroneStatus,
    Event,
    EventType,
    Priority,
    ToolExecution,
)
from aeromind.repositories.domain import EventRepository
from aeromind.schemas.api import DroneCreate
from aeromind.services.domain import DroneService


@pytest.fixture
def client_and_session() -> Iterator[tuple[TestClient, Session]]:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    session = Session(engine)
    app = create_app()
    app.dependency_overrides[get_session] = lambda: session
    app.dependency_overrides[simulation_get_session] = lambda: session
    with TestClient(app) as client:
        yield client, session
    session.close()


def _event(session: Session, *, event_id: str, severity: Priority) -> Drone:
    drone = DroneService(session).register(
        DroneCreate(
            drone_id=f"DR-{event_id}",
            name="Agent API contract simulation drone",
            latitude=37.42,
            longitude=-122.08,
            battery_percentage=72,
            temperature=22,
            gps_accuracy=1,
        )
    )
    EventRepository(session).create(
        Event(
            event_id=event_id,
            drone_id=drone.id,
            event_type=EventType.INTRUSION,
            severity=severity,
            confidence=0.91,
            description="Simulated restricted-zone event",
            metadata_={"restricted_zone": True, "simulated": True},
        )
    )
    session.commit()
    return drone


def test_agent_run_response_is_typed_safe_and_preserves_safe_execution_metadata(
    client_and_session: tuple[TestClient, Session],
) -> None:
    client, session = client_and_session
    _event(session, event_id="API-SAFE", severity=Priority.HIGH)

    response = client.post("/agent/run", json={"event_id": "API-SAFE", "execute_tools": True})

    assert response.status_code == 200
    body = response.json()
    assert set(body) == {
        "run_id",
        "decision",
        "risk_assessment",
        "mission_plan",
        "perception",
        "knowledge",
        "memory_count",
        "recorded_memory_ids",
        "warning_count",
        "tool_requests",
        "tool_results",
        "error_types",
        "execution_status",
    }
    assert body["decision"]["decision"] == "RAISE_ALERT"
    assert body["risk_assessment"]["risk_level"] == "HIGH"
    assert [item["name"] for item in body["tool_requests"]] == [
        "get_drone_status",
        "raise_alert",
    ]
    assert all(set(item) == {"tool_name", "status"} for item in body["tool_results"])
    assert all(key not in _all_keys(body) for key in _unsafe_keys())


def test_agent_history_and_tool_history_filter_persisted_internal_payloads(
    client_and_session: tuple[TestClient, Session],
) -> None:
    client, session = client_and_session
    _event(session, event_id="API-HISTORY", severity=Priority.HIGH)
    run = client.post("/agent/run", json={"event_id": "API-HISTORY", "execute_tools": True})
    run_id = run.json()["run_id"]
    record = session.query(AgentRun).filter_by(run_id=run_id).one()
    record.payload = {
        "requested_tools": ["get_drone_status", "not_a_registered_tool", "secret-tool-name"],
        "prompt": "must-not-leak",
        "environment": {"API_KEY": "must-not-leak"},
    }
    execution = session.query(ToolExecution).filter_by(run_id=record.id).first()
    assert execution is not None
    execution.payload = {
        "arguments": {"token": "must-not-leak"},
        "result": {"embedding": [1.0]},
    }
    session.commit()

    history = client.get(f"/agent/runs/{run_id}")
    tools = client.get(f"/agent/runs/{run_id}/tools")

    assert history.status_code == 200 and tools.status_code == 200
    assert history.json() == {
        "run_id": run_id,
        "status": "COMPLETED",
        "execution_status": "COMPLETED",
        "final_decision": "RAISE_ALERT",
        "error_type": None,
        "requested_tool_names": ["get_drone_status"],
        "requested_tool_count": 1,
    }
    assert all(set(item) == {"tool_name", "status"} for item in tools.json())
    assert "must-not-leak" not in f"{history.text}{tools.text}"
    assert all(
        key not in _all_keys(history.json()) | _all_keys(tools.json()) for key in _unsafe_keys()
    )


def test_agent_run_missing_resource_and_malformed_request_keep_http_semantics(
    client_and_session: tuple[TestClient, Session],
) -> None:
    client, _ = client_and_session

    assert client.post("/agent/run", json={"event_id": "MISSING"}).status_code == 404
    assert client.post("/agent/run", json={"execute_tools": True}).status_code == 422
    assert client.get("/agent/runs/missing-run").status_code == 404
    assert client.get("/agent/runs/missing-run/tools").status_code == 404


def test_approval_required_agent_run_remains_pending_and_simulation_only(
    client_and_session: tuple[TestClient, Session],
) -> None:
    client, session = client_and_session
    drone = _event(session, event_id="API-CRITICAL", severity=Priority.CRITICAL)

    response = client.post("/agent/run", json={"event_id": "API-CRITICAL", "execute_tools": True})

    assert response.status_code == 200
    body = response.json()
    assert body["decision"]["decision"] == "REQUEST_HUMAN_APPROVAL"
    assert body["execution_status"] == "REQUIRES_APPROVAL"
    assert body["tool_results"] == [{"tool_name": "return_to_home", "status": "REQUIRES_APPROVAL"}]
    assert session.query(Approval).one().status == "PENDING"
    session.refresh(drone)
    assert drone.status == DroneStatus.AVAILABLE


def test_approval_api_filters_persisted_tool_arguments(
    client_and_session: tuple[TestClient, Session],
) -> None:
    client, session = client_and_session
    _event(session, event_id="API-APPROVAL", severity=Priority.CRITICAL)
    client.post("/agent/run", json={"event_id": "API-APPROVAL", "execute_tools": True})
    approval = session.query(Approval).one()
    approval.payload = {"call": {"drone_id": "DR-API-APPROVAL", "token": "must-not-leak"}}
    session.commit()

    listed = client.get("/approvals")

    assert listed.status_code == 200
    assert listed.json() == [
        {"approval_id": str(approval.id), "status": "PENDING", "tool_name": "return_to_home"}
    ]
    assert "must-not-leak" not in listed.text
    assert "payload" not in _all_keys(listed.json())


def _unsafe_keys() -> set[str]:
    return {
        "prompt",
        "reasoning",
        "reason_summary",
        "description",
        "image",
        "image_bytes",
        "embedding",
        "vector",
        "content",
        "memory_context",
        "retrieved_chunks",
        "payload",
        "arguments",
        "credentials",
        "api_key",
        "environment",
    }


def _all_keys(value: object) -> set[str]:
    if isinstance(value, dict):
        return set(value) | set().union(*(_all_keys(item) for item in value.values()))
    if isinstance(value, list):
        return set().union(*(_all_keys(item) for item in value))
    return set()
