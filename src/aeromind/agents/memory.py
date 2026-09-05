from __future__ import annotations

from aeromind.schemas.memory import MemorySearch
from aeromind.services.memory import MemoryService


class MemoryRetrievalAgent:
    """Supplies prior operational evidence; it cannot authorize actions."""

    def __init__(self, service: MemoryService) -> None:
        self.service = service

    def run(self, state: dict) -> dict:
        event = state["incoming_event"]
        mission = state.get("mission_context")
        drone = state.get("drone_context")
        query = " ".join(
            part
            for part in [event.event_type.value, event.description, "operational outcome"]
            if part
        )
        result = self.service.retrieve_memories(
            MemorySearch(
                query=query,
                mission_id=mission.id if mission else None,
                agent_run_id=state.get("agent_run_id"),
                drone_id=drone.id if drone else None,
            )
        )
        return {"memory_context": result.memories}


class MemoryRecordingAgent:
    def __init__(self, service: MemoryService) -> None:
        self.service = service

    def run(self, state: dict) -> dict:
        records = self.service.record_run_outcomes(state)
        return {"recorded_memory_ids": [str(record.id) for record in records]}
