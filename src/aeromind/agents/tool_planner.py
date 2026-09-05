from aeromind.schemas.agents import RecommendedAction
from aeromind.tools.definitions import ToolCall


class ToolPlanner:
    def run(self, state: dict) -> dict:
        decision = state["decision"].decision
        drone = state.get("drone_context")
        mapping = {
            RecommendedAction.INVESTIGATE: ["get_drone_status", "capture_image"],
            RecommendedAction.RAISE_ALERT: ["get_drone_status", "raise_alert"],
            RecommendedAction.REQUEST_HUMAN_APPROVAL: ["return_to_home"],
            RecommendedAction.RETURN_TO_HOME: ["return_to_home"],
        }
        calls = [
            ToolCall(
                name=name,
                arguments=(
                    {"description": "Simulated agent alert", "drone_id": drone.drone_id}
                    if name == "raise_alert" and drone
                    else {"drone_id": drone.drone_id}
                    if drone and name in {"get_drone_status", "capture_image", "return_to_home"}
                    else {}
                ),
                request_id=state["request_id"],
            )
            for name in mapping.get(decision, [])
        ]
        return {"tool_requests": calls, "tool_candidates": [call.name for call in calls]}
