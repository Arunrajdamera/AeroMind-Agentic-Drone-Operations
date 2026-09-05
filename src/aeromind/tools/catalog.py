from __future__ import annotations

import asyncio
from collections.abc import Callable
from dataclasses import dataclass
from math import asin, cos, radians, sin, sqrt

from pydantic import BaseModel

from aeromind.models.domain import Event, EventType, HealthStatus, Priority
from aeromind.providers.mock import MockWeatherProvider
from aeromind.repositories.domain import (
    DroneRepository,
    EventRepository,
    MissionRepository,
    TelemetryRepository,
)
from aeromind.schemas.api import TelemetryCreate
from aeromind.services.domain import DroneService, MissionService, TelemetryService
from aeromind.tools.definitions import (
    AlertInput,
    CaptureInput,
    DispatchInput,
    DistanceInput,
    DroneIdInput,
    MissionIdInput,
    MissionUpdateInput,
    TelemetryAnalysisInput,
    TelemetryInput,
    ToolRisk,
)

Handler = Callable[[BaseModel], dict[str, object]]


@dataclass(frozen=True)
class ToolDefinition:
    name: str
    description: str
    input_schema: type[BaseModel]
    output_schema: type[BaseModel]
    risk: ToolRisk
    requires_approval: bool
    idempotency: str
    handler: Handler


class ToolCatalog:
    def __init__(self) -> None:
        self._tools: dict[str, ToolDefinition] = {}

    def register(self, definition: ToolDefinition) -> None:
        if definition.name in self._tools:
            raise ValueError(f"Duplicate tool: {definition.name}")
        self._tools[definition.name] = definition

    def get(self, name: str) -> ToolDefinition | None:
        return self._tools.get(name)

    def list_tools(self) -> tuple[ToolDefinition, ...]:
        return tuple(self._tools.values())


class ToolOutput(BaseModel):
    data: dict[str, object]


def build_catalog(session: object) -> ToolCatalog:
    """Single authoritative registry for simulation tool metadata and handlers."""
    catalog = ToolCatalog()

    def status(value: DroneIdInput) -> dict[str, object]:
        drone = DroneRepository(session).get_by_drone_id(value.drone_id)
        if not drone:
            raise ValueError("missing drone")
        return {
            "drone_id": drone.drone_id,
            "status": drone.status.value,
            "battery_percentage": drone.battery_percentage,
            "gps_accuracy": drone.gps_accuracy,
        }

    def available(_: BaseModel) -> dict[str, object]:
        return {"drones": [d.drone_id for d in DroneRepository(session).list()]}

    def distance(value: DistanceInput) -> dict[str, object]:
        a, b = radians(value.latitude_a), radians(value.latitude_b)
        dlat = b - a
        dlon = radians(value.longitude_b - value.longitude_a)
        return {
            "distance_m": round(
                6371000 * 2 * asin(sqrt(sin(dlat / 2) ** 2 + cos(a) * cos(b) * sin(dlon / 2) ** 2)),
                2,
            )
        }

    def weather(_: BaseModel) -> dict[str, object]:
        return asyncio.run(MockWeatherProvider().get_weather(0, 0)).model_dump()

    def telemetry(value: TelemetryAnalysisInput) -> dict[str, object]:
        drone = DroneRepository(session).get_by_drone_id(value.drone_id)
        if not drone:
            raise ValueError("missing drone")
        rows = TelemetryRepository(session).list_for_drone(drone.id)
        battery = [x.battery_percentage for x in rows]
        return {
            "telemetry_count": len(rows),
            "average_battery": sum(battery) / len(battery) if battery else None,
            "warnings": ["No telemetry"] if not rows else [],
        }

    def mission(value: MissionIdInput) -> dict[str, object]:
        item = MissionRepository(session).get_by_mission_id(value.mission_id)
        if not item:
            raise ValueError("missing mission")
        return {"mission_id": item.mission_id, "status": item.status.value}

    def dispatch(value: DispatchInput) -> dict[str, object]:
        item = MissionService(session).assign(value.mission_id, value.drone_id)
        return {"mission_id": item.mission_id, "status": item.status.value}

    def home(value: DroneIdInput) -> dict[str, object]:
        drone = DroneService(session).change_status(value.drone_id, "RETURNING")
        return {"drone_id": drone.drone_id, "status": drone.status.value, "simulated": True}

    def capture(value: CaptureInput) -> dict[str, object]:
        return {
            "drone_id": value.drone_id,
            "artifact": "simulated://capture/" + value.drone_id,
            "simulated": True,
        }

    def alert(value: AlertInput) -> dict[str, object]:
        drone = DroneRepository(session).get_by_drone_id(value.drone_id) if value.drone_id else None
        event = Event(
            event_id=f"ALERT-{len(EventRepository(session).list()) + 1}",
            event_type=EventType.INTRUSION,
            severity=Priority.HIGH,
            confidence=1.0,
            description=value.description,
            drone_id=drone.id if drone else None,
            metadata_={"simulated": True, "alert": True},
        )
        EventRepository(session).create(event)
        return {"event_id": event.event_id, "simulated": True}

    def update(value: MissionUpdateInput) -> dict[str, object]:
        return {"mission_id": value.mission_id, "requested_status": value.status, "simulated": True}

    def record(value: TelemetryInput) -> dict[str, object]:
        item = TelemetryService(session).record(
            TelemetryCreate(
                drone_id=value.drone_id,
                latitude=value.latitude,
                longitude=value.longitude,
                altitude=value.altitude,
                speed=value.speed,
                battery_percentage=value.battery_percentage,
                temperature=value.temperature,
                gps_accuracy=value.gps_accuracy,
                health_status=HealthStatus.HEALTHY,
            )
        )
        return {"telemetry_id": str(item.id)}

    definitions = [
        (
            "get_drone_status",
            "Read simulated drone state",
            DroneIdInput,
            ToolRisk.LOW,
            False,
            "idempotent",
            status,
        ),
        (
            "get_available_drones",
            "List simulation fleet",
            BaseModel,
            ToolRisk.LOW,
            False,
            "idempotent",
            available,
        ),
        ("get_weather", "Read mock weather", BaseModel, ToolRisk.LOW, False, "idempotent", weather),
        (
            "calculate_distance",
            "Calculate distance",
            DistanceInput,
            ToolRisk.LOW,
            False,
            "idempotent",
            distance,
        ),
        (
            "get_mission_status",
            "Read mission",
            MissionIdInput,
            ToolRisk.LOW,
            False,
            "idempotent",
            mission,
        ),
        (
            "analyze_drone_telemetry",
            "Analyze telemetry",
            TelemetryAnalysisInput,
            ToolRisk.LOW,
            False,
            "idempotent",
            telemetry,
        ),
        (
            "dispatch_drone",
            "Simulated dispatch",
            DispatchInput,
            ToolRisk.HIGH,
            True,
            "state-transition",
            dispatch,
        ),
        (
            "return_to_home",
            "Simulated return",
            DroneIdInput,
            ToolRisk.HIGH,
            True,
            "state-transition",
            home,
        ),
        (
            "capture_image",
            "Simulated capture",
            CaptureInput,
            ToolRisk.MEDIUM,
            False,
            "idempotent",
            capture,
        ),
        (
            "raise_alert",
            "Persist simulated alert",
            AlertInput,
            ToolRisk.MEDIUM,
            False,
            "deduplicate-by-event",
            alert,
        ),
        (
            "update_mission",
            "Update simulated mission",
            MissionUpdateInput,
            ToolRisk.MEDIUM,
            False,
            "state-transition",
            update,
        ),
        (
            "record_telemetry",
            "Append simulated telemetry",
            TelemetryInput,
            ToolRisk.MEDIUM,
            False,
            "append-only",
            record,
        ),
    ]
    for name, description, input_schema, risk, approval, idempotency, handler in definitions:
        catalog.register(
            ToolDefinition(
                name, description, input_schema, ToolOutput, risk, approval, idempotency, handler
            )
        )
    return catalog
