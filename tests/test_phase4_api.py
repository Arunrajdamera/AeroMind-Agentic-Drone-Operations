from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from aeromind.api.routes.agents import get_session
from aeromind.api.routes.simulation import get_session as simulation_get_session
from aeromind.db.base import Base
from aeromind.main import create_app
from aeromind.models.domain import Approval, Event, EventType, MissionType, Priority
from aeromind.repositories.domain import EventRepository
from aeromind.schemas.api import DroneCreate, MissionCreate
from aeromind.services.domain import DroneService, MissionService
from aeromind.tools.definitions import ToolCall, ToolStatus
from aeromind.tools.executor import ToolExecutor


def api_client() -> tuple[TestClient, Session]:
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
    return TestClient(app), session


def test_simulation_initialize_persists_fleet_for_events() -> None:
    client, _ = api_client()
    initialized = client.post("/simulation/initialize")
    event = client.post(
        "/events",
        json={
            "event_id": "SIM-DR-01",
            "event_type": "INTRUSION",
            "severity": "HIGH",
            "confidence": 0.91,
            "description": "Simulated event",
            "drone_id": "DR-01",
        },
    )
    assert initialized.status_code == 200
    assert "DR-01" in initialized.json()["drones"]
    assert event.status_code == 201


def setup_intrusion(session: Session) -> Event:
    drone = DroneService(session).register(
        DroneCreate(
            drone_id="DR-04",
            name="Solar Farm",
            latitude=37.42,
            longitude=-122.08,
            battery_percentage=72,
            temperature=22,
            gps_accuracy=1,
        )
    )
    return EventRepository(session).create(
        Event(
            event_id="SOLAR-INTRUSION",
            drone_id=drone.id,
            event_type=EventType.INTRUSION,
            severity=Priority.HIGH,
            confidence=0.91,
            description="Simulated restricted-zone perimeter intrusion",
            metadata_={"restricted_zone": True, "object_type": "person", "simulated": True},
        )
    )


def test_agent_run_executes_safe_tool_and_history_is_persisted() -> None:
    client, session = api_client()
    setup_intrusion(session)
    session.commit()
    response = client.post(
        "/agent/run", json={"event_id": "SOLAR-INTRUSION", "execute_tools": True}
    )
    assert response.status_code == 200
    body = response.json()
    assert body["execution_status"] == "COMPLETED"
    assert body["tool_results"]
    history = client.get(f"/agent/runs/{body['run_id']}")
    tools = client.get(f"/agent/runs/{body['run_id']}/tools")
    assert history.status_code == 200 and tools.status_code == 200
    assert tools.json()[0]["status"] == "SUCCEEDED"


def test_execute_tools_false_creates_no_tool_execution() -> None:
    client, session = api_client()
    setup_intrusion(session)
    session.commit()
    response = client.post(
        "/agent/run", json={"event_id": "SOLAR-INTRUSION", "execute_tools": False}
    )
    assert response.status_code == 200
    assert response.json()["execution_status"] == "PLANNED"
    assert client.get(f"/agent/runs/{response.json()['run_id']}/tools").json() == []


def test_high_risk_unknown_and_invalid_calls_fail_closed() -> None:
    _, session = api_client()
    executor = ToolExecutor(session)
    high = executor.execute(
        ToolCall(
            name="dispatch_drone",
            arguments={"drone_id": "DR-X", "mission_id": "M-X"},
            request_id="x",
        )
    )
    unknown = executor.execute(ToolCall(name="unregistered", arguments={}, request_id="x"))
    invalid = executor.execute(ToolCall(name="get_drone_status", arguments={}, request_id="x"))
    assert high.status == ToolStatus.REQUIRES_APPROVAL
    assert unknown.status == ToolStatus.BLOCKED
    assert invalid.status == ToolStatus.FAILED


def test_approval_approve_reject_and_duplicate_transition() -> None:
    client, session = api_client()
    drone = DroneService(session).register(
        DroneCreate(
            drone_id="DR-99",
            name="Approval",
            latitude=1,
            longitude=2,
            battery_percentage=90,
            temperature=20,
            gps_accuracy=1,
        )
    )
    mission = MissionService(session).create(
        MissionCreate(
            mission_id="AP-01",
            mission_type=MissionType.PERIMETER_INSPECTION,
            priority=Priority.HIGH,
            target_latitude=1,
            target_longitude=2,
            objective="simulated",
        )
    )
    session.commit()
    pending = ToolExecutor(session).execute(
        ToolCall(
            name="dispatch_drone",
            arguments={"drone_id": drone.drone_id, "mission_id": mission.mission_id},
            request_id="approval",
        )
    )
    approval_id = session.query(Approval).one().id
    approved = client.post(f"/approvals/{approval_id}/approve")
    duplicate = client.post(f"/approvals/{approval_id}/approve")
    assert pending.status == ToolStatus.REQUIRES_APPROVAL
    assert approved.status_code == 200
    assert duplicate.status_code == 409


def test_rejected_and_expired_approvals_cannot_execute() -> None:
    client, session = api_client()
    first = ToolExecutor(session).execute(
        ToolCall(name="return_to_home", arguments={"drone_id": "DR-01"}, request_id="reject")
    )
    rejection_id = session.query(Approval).one().id
    assert first.status == ToolStatus.REQUIRES_APPROVAL
    assert client.post(f"/approvals/{rejection_id}/reject").status_code == 200
    assert client.post(f"/approvals/{rejection_id}/approve").status_code == 409
    second = ToolExecutor(session).execute(
        ToolCall(name="return_to_home", arguments={"drone_id": "DR-02"}, request_id="expire")
    )
    expired = session.query(Approval).filter(Approval.id != rejection_id).one()
    expired.expires_at = datetime.now(UTC) - timedelta(seconds=1)
    session.commit()
    assert second.status == ToolStatus.REQUIRES_APPROVAL
    assert client.post(f"/approvals/{expired.id}/approve").status_code == 409
    session.refresh(expired)
    assert expired.status == "EXPIRED"


def test_critical_agent_run_creates_return_home_approval_and_continues() -> None:
    client, session = api_client()
    drone = DroneService(session).register(
        DroneCreate(
            drone_id="DR-CRITICAL",
            name="Critical Simulation Drone",
            latitude=37.42,
            longitude=-122.08,
            battery_percentage=72,
            temperature=22,
            gps_accuracy=1,
        )
    )
    EventRepository(session).create(
        Event(
            event_id="SOLAR-CRITICAL",
            drone_id=drone.id,
            event_type=EventType.INTRUSION,
            severity=Priority.CRITICAL,
            confidence=0.91,
            description="Simulated critical perimeter intrusion",
            metadata_={"restricted_zone": True, "simulated": True},
        )
    )
    session.commit()
    run = client.post("/agent/run", json={"event_id": "SOLAR-CRITICAL", "execute_tools": True})
    body = run.json()
    assert run.status_code == 200
    assert body["decision"]["decision"] == "REQUEST_HUMAN_APPROVAL"
    assert body["tool_requests"][0]["name"] == "return_to_home"
    assert body["tool_results"][0]["status"] == "REQUIRES_APPROVAL"
    approval = session.query(Approval).one()
    assert approval.status == "PENDING" and approval.tool_name == "return_to_home"
    approved = client.post(f"/approvals/{approval.id}/approve")
    assert approved.status_code == 200
    assert approved.json()["execution"]["status"] == "SUCCEEDED"
    session.refresh(drone)
    assert drone.status.value == "RETURNING"
    assert client.post(f"/approvals/{approval.id}/approve").status_code == 409
