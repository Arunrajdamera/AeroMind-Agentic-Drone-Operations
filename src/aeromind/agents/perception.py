from aeromind.schemas.agents import PerceptionResult


class PerceptionAgent:
    def run(self, state: dict) -> dict:
        event = state["incoming_event"]
        metadata = event.metadata_ or {}
        restricted = bool(
            metadata.get(
                "restricted_zone", event.event_type.value in {"INTRUSION", "SUSPICIOUS_PERSON"}
            )
        )
        return {
            "perception_result": PerceptionResult(
                event_type=event.event_type.value,
                object_type=str(metadata.get("object_type", "unknown")),
                confidence=event.confidence,
                severity=event.severity.value,
                location=f"{event.latitude},{event.longitude}"
                if event.latitude is not None
                else None,
                restricted_zone=restricted,
                requires_investigation=restricted or event.severity.value in {"HIGH", "CRITICAL"},
                reason_summary="Normalized simulated event metadata; no real vision was used.",
            )
        }
