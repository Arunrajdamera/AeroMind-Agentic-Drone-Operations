from __future__ import annotations

from uuid import uuid4

from sqlalchemy.orm import Session

from aeromind.core.exceptions import DomainError
from aeromind.graph.workflow import build_workflow
from aeromind.models.domain import AgentRun
from aeromind.repositories.domain import DroneRepository, EventRepository, MissionRepository


class AgentOrchestrator:
    def __init__(self, session: Session) -> None:
        self.session = session

    def run_event_analysis(
        self,
        event_id: str,
        mission_id: str | None = None,
        drone_id: str | None = None,
        execute_tools: bool = False,
    ) -> dict:
        event = EventRepository(self.session).get_by_id(event_id)
        if not event:
            raise DomainError("Event not found")
        mission = (
            MissionRepository(self.session).get_by_mission_id(mission_id)
            if mission_id
            else event.mission
        )
        if mission_id and not mission:
            raise DomainError("Mission not found")
        drone = DroneRepository(self.session).get_by_drone_id(drone_id) if drone_id else event.drone
        if drone_id and not drone:
            raise DomainError("Drone not found")
        state = {
            "request_id": str(uuid4()),
            "run_id": str(uuid4()),
            "event_id": event_id,
            "mission_id": mission_id,
            "drone_id": drone_id,
            "incoming_event": event,
            "mission_context": mission,
            "drone_context": drone,
            "warnings": [],
            "errors": [],
            "execution_status": "RUNNING",
            "execute_tools": execute_tools,
        }
        record = AgentRun(run_id=state["run_id"], status="RUNNING")
        self.session.add(record)
        self.session.flush()
        state["agent_run_id"] = record.id
        try:
            result = dict(build_workflow(self.session).invoke(state))
            record.status, record.execution_status = "COMPLETED", result["execution_status"]
            record.final_decision = (
                result.get("decision").decision.value if result.get("decision") else None
            )
            record.payload = {"requested_tools": result.get("tool_candidates", [])}
            self.session.commit()
            return result
        except Exception as error:
            record.status, record.execution_status, record.error = (
                "FAILED",
                "FAILED",
                type(error).__name__,
            )
            self.session.commit()
            return {
                **state,
                "errors": [f"workflow failure: {type(error).__name__}"],
                "execution_status": "FAILED",
            }
