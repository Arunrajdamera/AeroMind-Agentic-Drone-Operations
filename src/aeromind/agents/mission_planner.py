from sqlalchemy.orm import Session

from aeromind.models.domain import DroneStatus
from aeromind.repositories.domain import DroneRepository
from aeromind.schemas.agents import MissionPlan, RecommendedAction


class MissionPlannerAgent:
    def __init__(self, session: Session) -> None:
        self.session = session

    def run(self, state: dict) -> dict:
        mission = state.get("mission_context")
        drones = DroneRepository(self.session).list()
        eligible = [
            d
            for d in drones
            if d.status == DroneStatus.AVAILABLE
            and d.battery_percentage >= 25
            and d.health_status.value == "HEALTHY"
        ]
        target_lat, target_lon = (
            (mission.target_latitude, mission.target_longitude) if mission else (0, 0)
        )
        selected = min(
            eligible,
            key=lambda d: abs(d.latitude - target_lat) + abs(d.longitude - target_lon),
            default=None,
        )
        constraints = [] if selected else ["No eligible simulated drone available"]
        return {
            "mission_plan": MissionPlan(
                selected_drone_id=selected.drone_id if selected else None,
                objective=mission.objective if mission else "Analyze simulated event",
                mission_type=mission.mission_type.value if mission else "INCIDENT_RESPONSE",
                priority=mission.priority.value if mission else "HIGH",
                planned_action=RecommendedAction.INVESTIGATE
                if selected
                else RecommendedAction.REQUEST_HUMAN_APPROVAL,
                constraints=constraints,
                reason_summary="Selected by availability, battery, health, and proximity.",
            ),
            "drone_context": selected,
            "warnings": constraints,
        }
