from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from aeromind.agents.decision import DecisionAgent
from aeromind.agents.memory import MemoryRetrievalAgent
from aeromind.api.routes.memory import get_session
from aeromind.core.exceptions import DomainError
from aeromind.graph.workflow import build_workflow
from aeromind.main import create_app
from aeromind.models.domain import (
    AgentRun,
    Approval,
    Drone,
    DroneStatus,
    Event,
    EventType,
    HealthStatus,
    MemoryRecord,
    MemoryScope,
    MemorySourceType,
    MemoryStatus,
    MemoryType,
    Mission,
    MissionStatus,
    MissionType,
    Priority,
    ToolExecution,
)
from aeromind.providers.mock import MockEmbeddingProvider
from aeromind.schemas.agents import (
    KnowledgeResult,
    PerceptionResult,
    RecommendedAction,
    RiskAssessment,
    RiskLevel,
)
from aeromind.schemas.memory import MemoryCreate, MemoryEvidence, MemorySearch, MemorySearchResult
from aeromind.services.memory import MemoryService
from aeromind.tools.definitions import ToolCall, ToolExecutionResult, ToolStatus
from aeromind.tools.executor import ToolExecutor


def memory_client() -> tuple[TestClient, Session]:
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    from aeromind.db.base import Base

    Base.metadata.create_all(engine)
    session = Session(engine)
    app = create_app()
    app.dependency_overrides[get_session] = lambda: session
    return TestClient(app), session


def memory_data(**overrides: object) -> dict[str, object]:
    data: dict[str, object] = {
        "memory_type": "MISSION_OUTCOME",
        "scope": "MISSION",
        "content": "Mission M-001 completed a simulated perimeter inspection.",
        "structured_data": {"mission": "M-001", "simulated": True},
        "source": "mission_service",
        "source_type": "MISSION",
        "source_id": "M-001",
        "confidence": 0.95,
        "importance": 0.85,
    }
    data.update(overrides)
    return data


def create_memory(session: Session, **overrides: object) -> MemoryRecord:
    item, _ = MemoryService(session).create_memory(MemoryCreate(**memory_data(**overrides)))
    session.commit()
    return item


def make_mission(session: Session, mission_id: str = "M-001") -> Mission:
    mission = Mission(
        mission_id=mission_id,
        mission_type=MissionType.PERIMETER_INSPECTION,
        priority=Priority.HIGH,
        target_latitude=37.42,
        target_longitude=-122.08,
        objective="Simulated solar-farm perimeter inspection",
        status=MissionStatus.PLANNED,
    )
    session.add(mission)
    session.flush()
    return mission


def make_drone(session: Session, drone_id: str = "DR-MEM") -> Drone:
    drone = Drone(
        drone_id=drone_id,
        name="Memory Test Drone",
        status=DroneStatus.AVAILABLE,
        latitude=37.42,
        longitude=-122.08,
        battery_percentage=80,
        temperature=20,
        gps_accuracy=1,
        health_status=HealthStatus.HEALTHY,
    )
    session.add(drone)
    session.flush()
    return drone


def make_event(session: Session, mission: Mission, drone: Drone, critical: bool = False) -> Event:
    event = Event(
        event_id=f"EVENT-{uuid4()}",
        mission_id=mission.id,
        drone_id=drone.id,
        event_type=EventType.INTRUSION,
        severity=Priority.CRITICAL if critical else Priority.HIGH,
        confidence=0.91,
        description="Simulated restricted-zone perimeter intrusion",
        metadata_={"restricted_zone": True, "simulated": True},
    )
    session.add(event)
    session.flush()
    return event


def test_create_structured_memory_and_deduplicates_identical_provenance() -> None:
    client, session = memory_client()
    first = client.post("/memory", json=memory_data())
    second = client.post("/memory", json=memory_data())
    assert first.status_code == second.status_code == 201
    body = first.json()
    assert body["memory_type"] == "MISSION_OUTCOME"
    assert body["scope"] == "MISSION"
    assert body["confidence"] == 0.95 and body["importance"] == 0.85
    assert body["source_type"] == "MISSION" and body["source_id"] == "M-001"
    assert body["status"] == "ACTIVE" and body["created_at"] and body["updated_at"]
    assert body["memory_id"] == second.json()["memory_id"]
    record = session.query(MemoryRecord).one()
    assert len(record.embedding) == 8 and record.embedding_model == "mock-embedding-v1"


def test_memory_creation_rejects_malformed_values() -> None:
    client, _ = memory_client()
    assert client.post("/memory", json=memory_data(content="   ")).status_code == 422
    assert client.post("/memory", json=memory_data(confidence=1.1)).status_code == 422
    assert client.post("/memory", json=memory_data(importance=-0.1)).status_code == 422
    assert client.post("/memory", json=memory_data(memory_type="NOT_A_TYPE")).status_code == 422


def test_memory_search_returns_ordered_provenance_and_honors_top_k() -> None:
    _, session = memory_client()
    first = create_memory(session, content="Solar farm intrusion requires simulated escalation.")
    create_memory(
        session, content="Routine simulated thermal inspection completed.", source_id="M-002"
    )
    result = MemoryService(session).retrieve_memories(
        MemorySearch(query=first.content, top_k=1, similarity_threshold=0)
    )
    assert len(result.memories) == 1
    evidence = result.memories[0]
    assert evidence.memory_id == first.id and evidence.similarity_score == 1.0
    assert evidence.source == "mission_service" and evidence.source_id == "M-001"
    assert evidence.structured_data["simulated"] is True


def test_memory_search_filters_confidence_and_mission_scope() -> None:
    _, session = memory_client()
    mission_a, mission_b = make_mission(session, "M-A"), make_mission(session, "M-B")
    item_a = create_memory(
        session,
        mission_id=mission_a.id,
        source_id="M-A",
        content="Mission A simulated intrusion outcome.",
        confidence=0.9,
    )
    create_memory(
        session,
        mission_id=mission_b.id,
        source_id="M-B",
        content="Mission B simulated intrusion outcome.",
        confidence=0.2,
    )
    result = MemoryService(session).retrieve_memories(
        MemorySearch(
            query="simulated intrusion outcome",
            mission_id=mission_a.id,
            min_confidence=0.8,
            similarity_threshold=0,
        )
    )
    assert [item.memory_id for item in result.memories] == [item_a.id]


def test_unscoped_memory_search_remains_backward_compatible() -> None:
    _, session = memory_client()
    first = create_memory(session, content="Unscoped search alpha", source_id="unscoped-a")
    second = create_memory(session, content="Unscoped search beta", source_id="unscoped-b")
    result = MemoryService(session).retrieve_memories(
        MemorySearch(query="Unscoped search alpha", similarity_threshold=-1)
    )
    assert {item.memory_id for item in result.memories} == {first.id, second.id}


def test_memory_search_isolates_drone_and_agent_run_identifiers() -> None:
    _, session = memory_client()
    drone_a, drone_b = make_drone(session, "DR-SCOPE-A"), make_drone(session, "DR-SCOPE-B")
    run_a = AgentRun(run_id="RUN-SCOPE-A", status="COMPLETED")
    run_b = AgentRun(run_id="RUN-SCOPE-B", status="COMPLETED")
    session.add_all([run_a, run_b])
    session.flush()
    scoped_a = create_memory(
        session,
        content="Drone A run A scoped record.",
        source_id="scope-a",
        drone_id=drone_a.id,
        agent_run_id=run_a.id,
    )
    scoped_b = create_memory(
        session,
        content="Drone B run B scoped record.",
        source_id="scope-b",
        drone_id=drone_b.id,
        agent_run_id=run_b.id,
    )
    by_drone = MemoryService(session).retrieve_memories(
        MemorySearch(query="scoped record", drone_id=drone_a.id, similarity_threshold=-1)
    )
    by_run = MemoryService(session).retrieve_memories(
        MemorySearch(query="scoped record", agent_run_id=run_a.id, similarity_threshold=-1)
    )
    assert [item.memory_id for item in by_drone.memories] == [scoped_a.id]
    assert [item.memory_id for item in by_run.memories] == [scoped_a.id]
    assert scoped_b.id not in {item.memory_id for item in by_drone.memories}


def test_memory_search_combines_scope_filters_and_excludes_null_scope_values() -> None:
    _, session = memory_client()
    mission_a, mission_b = make_mission(session, "M-COMB-A"), make_mission(session, "M-COMB-B")
    drone_a, drone_b = make_drone(session, "DR-COMB-A"), make_drone(session, "DR-COMB-B")
    exact = create_memory(
        session,
        content="Combined scope target memory.",
        source_id="combined-exact",
        mission_id=mission_a.id,
        drone_id=drone_a.id,
    )
    create_memory(
        session,
        content="Combined wrong drone memory.",
        source_id="combined-drone",
        mission_id=mission_a.id,
        drone_id=drone_b.id,
    )
    create_memory(
        session,
        content="Combined wrong mission memory.",
        source_id="combined-mission",
        mission_id=mission_b.id,
        drone_id=drone_a.id,
    )
    create_memory(session, content="Combined null scope memory.", source_id="combined-null")
    result = MemoryService(session).retrieve_memories(
        MemorySearch(
            query="Combined scope target memory.",
            mission_id=mission_a.id,
            drone_id=drone_a.id,
            similarity_threshold=-1,
        )
    )
    assert [item.memory_id for item in result.memories] == [exact.id]


def test_memory_search_applies_lifecycle_confidence_and_top_k_after_scope() -> None:
    client, session = memory_client()
    mission = make_mission(session, "M-LIFE")
    active = create_memory(
        session,
        content="Scoped active confidence memory.",
        source_id="life-active",
        mission_id=mission.id,
        confidence=0.9,
    )
    archived = create_memory(
        session,
        content="Scoped archived confidence memory.",
        source_id="life-archived",
        mission_id=mission.id,
        confidence=0.9,
    )
    low_confidence = create_memory(
        session,
        content="Scoped low confidence memory.",
        source_id="life-low",
        mission_id=mission.id,
        confidence=0.1,
    )
    assert client.post(f"/memory/{archived.id}/archive").status_code == 200
    result = MemoryService(session).retrieve_memories(
        MemorySearch(
            query="Scoped active confidence memory.",
            mission_id=mission.id,
            min_confidence=0.8,
            top_k=1,
            similarity_threshold=-1,
        )
    )
    assert [item.memory_id for item in result.memories] == [active.id]
    assert low_confidence.id not in {item.memory_id for item in result.memories}


def test_memory_search_api_rejects_malformed_scope_uuids() -> None:
    client, _ = memory_client()
    for field in ("mission_id", "agent_run_id", "drone_id"):
        assert (
            client.post("/memory/search", json={"query": "scope", field: "not-a-uuid"}).status_code
            == 422
        )


def test_memory_search_excludes_archived_invalidated_and_expired_records() -> None:
    client, session = memory_client()
    archived = create_memory(session, content="Archived memory", source_id="archive")
    invalidated = create_memory(session, content="Invalidated memory", source_id="invalidate")
    expired = create_memory(
        session,
        content="Expired memory",
        source_id="expired",
        expires_at=datetime.now(UTC) - timedelta(seconds=1),
    )
    assert client.post(f"/memory/{archived.id}/archive").status_code == 200
    assert client.post(f"/memory/{invalidated.id}/invalidate").status_code == 200
    result = MemoryService(session).retrieve_memories(
        MemorySearch(query="memory", similarity_threshold=-1)
    )
    assert {item.memory_id for item in result.memories}.isdisjoint(
        {archived.id, invalidated.id, expired.id}
    )
    session.refresh(expired)
    assert expired.status == MemoryStatus.EXPIRED


def test_get_expired_memory_documents_current_uncommitted_expiry_gap() -> None:
    client, session = memory_client()
    item = create_memory(
        session,
        content="GET expiry behavior",
        source_id="get-expiry",
        expires_at=datetime.now(UTC) - timedelta(seconds=1),
    )
    response = client.get(f"/memory/{item.id}")
    assert response.status_code == 200 and response.json()["status"] == "EXPIRED"
    # Current implementation marks expiry in the request session but GET does not commit it.
    session.rollback()
    assert session.get(MemoryRecord, item.id).status == MemoryStatus.ACTIVE


class RetrievalSpy:
    def __init__(self, evidence: MemoryEvidence) -> None:
        self.evidence = evidence
        self.request: MemorySearch | None = None

    def retrieve_memories(self, request: MemorySearch) -> MemorySearchResult:
        self.request = request
        return MemorySearchResult(memories=[self.evidence])


def test_memory_retrieval_agent_populates_typed_state_and_preserves_provenance() -> None:
    evidence = MemoryEvidence(
        memory_id=uuid4(),
        memory_type=MemoryType.INCIDENT_PATTERN,
        scope=MemoryScope.MISSION,
        content="Prior simulated GPS instability.",
        similarity_score=0.8,
        confidence=0.9,
        importance=0.8,
        source="event_service",
        source_type=MemorySourceType.EVENT,
        source_id="EV-1",
        structured_data={"zone": "B"},
    )
    spy = RetrievalSpy(evidence)
    event = type("Event", (), {"event_type": EventType.GPS_ANOMALY, "description": "Zone B"})()
    run_id, drone_id = uuid4(), uuid4()
    state = MemoryRetrievalAgent(spy).run(
        {
            "incoming_event": event,
            "mission_context": None,
            "agent_run_id": run_id,
            "drone_context": type("Drone", (), {"id": drone_id})(),
        }
    )
    assert spy.request is not None and "GPS_ANOMALY" in spy.request.query
    assert spy.request.agent_run_id == run_id and spy.request.drone_id == drone_id
    assert state["memory_context"] == [evidence]


def test_workflow_executes_memory_retrieval_and_decision_receives_context() -> None:
    _, session = memory_client()
    mission, drone = make_mission(session), make_drone(session)
    event = make_event(session, mission, drone)
    run_id = str(uuid4())
    run_record = AgentRun(run_id=run_id, status="RUNNING")
    session.add(run_record)
    session.flush()
    memory = create_memory(
        session,
        mission_id=mission.id,
        agent_run_id=run_record.id,
        drone_id=drone.id,
        content="INTRUSION simulated operational outcome.",
        source_id="M-001",
    )
    session.commit()
    result = dict(
        build_workflow(session).invoke(
            {
                "request_id": str(uuid4()),
                "run_id": run_id,
                "agent_run_id": run_record.id,
                "incoming_event": event,
                "mission_context": mission,
                "drone_context": drone,
                "execute_tools": False,
            }
        )
    )
    assert result["memory_context"] and result["memory_context"][0].memory_id == memory.id
    assert result["evidence_assessment"].memory_count == 1
    assert result["decision"].evidence_assessment == result["evidence_assessment"]
    assert "prior memory records" in result["decision"].reason_summary


def test_decision_agent_memory_context_does_not_override_critical_approval() -> None:
    evidence = MemoryEvidence(
        memory_id=uuid4(),
        memory_type=MemoryType.TOOL_OUTCOME,
        scope=MemoryScope.MISSION,
        content="Prior return completed.",
        similarity_score=1,
        confidence=1,
        importance=1,
        source="test",
        source_type=MemorySourceType.SYSTEM_OBSERVATION,
        source_id="test",
    )
    result = DecisionAgent().run(
        {
            "risk_assessment": RiskAssessment(
                risk_level=RiskLevel.CRITICAL,
                risk_score=90,
                risk_factors=["critical"],
                recommended_action=RecommendedAction.REQUEST_HUMAN_APPROVAL,
                requires_human_approval=True,
                reason_summary="test",
            ),
            "perception_result": PerceptionResult(
                event_type="INTRUSION",
                object_type="person",
                confidence=0.9,
                severity="CRITICAL",
                location=None,
                restricted_zone=True,
                requires_investigation=True,
                reason_summary="test",
            ),
            "knowledge_result": KnowledgeResult(relevant=False, policy="", sources=[]),
            "memory_context": [evidence],
        }
    )
    assert result["decision"].decision == RecommendedAction.REQUEST_HUMAN_APPROVAL
    assert result["decision"].requires_approval


def test_critical_memory_path_does_not_bypass_persisted_approval() -> None:
    client, session = memory_client()
    mission, drone = make_mission(session), make_drone(session)
    event = make_event(session, mission, drone, critical=True)
    create_memory(
        session,
        mission_id=mission.id,
        content="Prior simulated return-to-home required approval.",
        source_id="M-001",
    )
    session.commit()
    response = client.post("/agent/run", json={"event_id": event.event_id, "execute_tools": True})
    assert response.status_code == 200
    body = response.json()
    assert body["decision"]["decision"] == "REQUEST_HUMAN_APPROVAL"
    assert body["tool_results"][0]["status"] == "REQUIRES_APPROVAL"
    approval = session.query(Approval).one()
    session.refresh(drone)
    assert drone.status == DroneStatus.AVAILABLE
    approved = client.post(f"/approvals/{approval.id}/approve")
    assert approved.status_code == 200 and approved.json()["execution"]["status"] == "SUCCEEDED"
    session.refresh(drone)
    assert drone.status == DroneStatus.RETURNING


def test_memory_recording_persists_safe_decision_and_initial_tool_outcomes() -> None:
    client, session = memory_client()
    mission, drone = make_mission(session), make_drone(session)
    event = make_event(session, mission, drone, critical=True)
    session.commit()
    result = client.post("/agent/run", json={"event_id": event.event_id, "execute_tools": True})
    assert result.status_code == 200
    records = session.query(MemoryRecord).all()
    assert {record.memory_type for record in records} >= {
        MemoryType.DECISION_OUTCOME,
        MemoryType.TOOL_OUTCOME,
    }
    assert all(record.source_type == MemorySourceType.AGENT_RUN for record in records)
    assert all("prompt" not in record.structured_data for record in records)


def test_approved_continuation_records_provenance_backed_succeeded_tool_memory() -> None:
    client, session = memory_client()
    mission, drone = make_mission(session), make_drone(session)
    event = make_event(session, mission, drone, critical=True)
    session.commit()
    run = client.post("/agent/run", json={"event_id": event.event_id, "execute_tools": True})
    approval = session.query(Approval).one()
    approved = client.post(f"/approvals/{approval.id}/approve")
    succeeded = session.query(ToolExecution).filter_by(status="SUCCEEDED").one()
    outcome = next(
        record
        for record in session.query(MemoryRecord).all()
        if record.structured_data.get("approval_id") == str(approval.id)
    )
    assert approved.status_code == 200 and succeeded.tool_name == "return_to_home"
    assert outcome.structured_data["execution_status"] == "SUCCEEDED"
    assert outcome.structured_data["tool"] == "return_to_home"
    assert outcome.source_type == MemorySourceType.APPROVAL
    assert outcome.agent_run_id is not None and outcome.drone_id == drone.id
    assert outcome.mission_id is None and run.json()["run_id"]


def test_approval_outcome_preserves_mission_provenance_when_tool_payload_includes_it() -> None:
    client, session = memory_client()
    mission, drone = make_mission(session), make_drone(session)
    run = AgentRun(run_id="DISPATCH-APPROVAL-RUN", status="COMPLETED")
    session.add(run)
    session.commit()
    pending = ToolExecutor(session).execute(
        ToolCall(
            name="dispatch_drone",
            arguments={"drone_id": drone.drone_id, "mission_id": mission.mission_id},
            request_id="dispatch-memory",
        ),
        run.run_id,
    )
    approval = session.query(Approval).one()
    approved = client.post(f"/approvals/{approval.id}/approve")
    outcome = next(
        record
        for record in session.query(MemoryRecord).all()
        if record.structured_data.get("approval_id") == str(approval.id)
    )
    assert pending.status == ToolStatus.REQUIRES_APPROVAL
    assert approved.status_code == 200
    assert outcome.mission_id == mission.id and outcome.drone_id == drone.id
    assert outcome.agent_run_id == run.id and outcome.structured_data["tool"] == "dispatch_drone"


def test_rejected_and_expired_approvals_record_terminal_memory_without_execution() -> None:
    client, session = memory_client()
    mission, drone = make_mission(session), make_drone(session)
    event = make_event(session, mission, drone, critical=True)
    session.commit()
    client.post("/agent/run", json={"event_id": event.event_id, "execute_tools": True})
    rejected = session.query(Approval).one()
    assert client.post(f"/approvals/{rejected.id}/reject").status_code == 200
    rejected_memory = next(
        record
        for record in session.query(MemoryRecord).all()
        if record.structured_data.get("approval_id") == str(rejected.id)
    )
    assert rejected_memory.structured_data["approval_status"] == "REJECTED"
    assert rejected_memory.structured_data["execution_status"] == "REJECTED"
    assert session.query(ToolExecution).filter_by(status="SUCCEEDED").count() == 0

    second_event = make_event(session, mission, drone, critical=True)
    session.commit()
    client.post("/agent/run", json={"event_id": second_event.event_id, "execute_tools": True})
    expiring = session.query(Approval).filter_by(status="PENDING").one()
    assert client.post(f"/approvals/{expiring.id}/expire").status_code == 200
    expiry_memory = next(
        record
        for record in session.query(MemoryRecord).all()
        if record.structured_data.get("approval_id") == str(expiring.id)
    )
    assert expiry_memory.structured_data["approval_status"] == "EXPIRED"
    assert expiry_memory.structured_data["execution_status"] == "EXPIRED"


def test_duplicate_approval_transition_does_not_create_duplicate_outcome_memory() -> None:
    client, session = memory_client()
    mission, drone = make_mission(session), make_drone(session)
    event = make_event(session, mission, drone, critical=True)
    session.commit()
    client.post("/agent/run", json={"event_id": event.event_id, "execute_tools": True})
    approval = session.query(Approval).one()
    assert client.post(f"/approvals/{approval.id}/approve").status_code == 200
    assert client.post(f"/approvals/{approval.id}/approve").status_code == 409
    assert (
        session.query(MemoryRecord).filter(MemoryRecord.content.contains(str(approval.id))).count()
        == 1
    )


def test_failed_execution_outcome_is_recorded_without_mutating_its_status() -> None:
    _, session = memory_client()
    approval = Approval(
        status="APPROVED",
        tool_name="return_to_home",
        payload={"call": {"drone_id": "DR-FAIL"}, "run_id": None},
    )
    session.add(approval)
    session.flush()
    outcome, created = MemoryService(session).record_approval_outcome(
        approval,
        ToolExecutionResult(
            execution_id="failure",
            tool_name="return_to_home",
            status=ToolStatus.FAILED,
            error="Tool execution failed",
        ),
    )
    assert created and outcome.structured_data["execution_status"] == "FAILED"
    assert outcome.structured_data["approval_status"] == "APPROVED"


def test_memory_recording_failure_does_not_change_approved_execution(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client, session = memory_client()
    mission, drone = make_mission(session), make_drone(session)
    event = make_event(session, mission, drone, critical=True)
    session.commit()
    client.post("/agent/run", json={"event_id": event.event_id, "execute_tools": True})
    approval = session.query(Approval).one()

    def fail_recording(
        self: MemoryService, *args: object, **kwargs: object
    ) -> tuple[MemoryRecord, bool]:
        del self, args, kwargs
        raise DomainError("simulated memory persistence failure")

    monkeypatch.setattr(MemoryService, "record_approval_outcome", fail_recording)
    response = client.post(f"/approvals/{approval.id}/approve")
    session.refresh(approval)
    session.refresh(drone)
    assert response.status_code == 200 and approval.status == "APPROVED"
    assert drone.status == DroneStatus.RETURNING


def test_memory_service_explicitly_defaults_to_mock_embedding_provider() -> None:
    _, session = memory_client()
    assert isinstance(MemoryService(session).provider, MockEmbeddingProvider)


def test_memory_retrieval_cannot_execute_tools_directly() -> None:
    _, session = memory_client()
    create_memory(session, content="Historical simulated intrusion", source_id="safe-boundary")
    before = session.query(ToolExecution).count()
    MemoryRetrievalAgent(MemoryService(session)).run(
        {
            "incoming_event": type(
                "Event", (), {"event_type": EventType.INTRUSION, "description": "simulated"}
            )(),
            "mission_context": None,
        }
    )
    assert session.query(ToolExecution).count() == before
