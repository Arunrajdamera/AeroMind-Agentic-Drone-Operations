from __future__ import annotations

import random

from sqlalchemy.orm import Session

from aeromind.core.config import Settings, get_settings
from aeromind.core.exceptions import SimulationError
from aeromind.models.domain import DroneStatus, EventType, HealthStatus, Severity
from aeromind.schemas.api import DroneCreate, EventCreate, TelemetryCreate
from aeromind.services.domain import DroneService, EventService, TelemetryService


class DroneSimulator:
    """Deterministic simulator; it only writes simulated database data."""

    def __init__(self, session: Session, settings: Settings | None = None) -> None:
        self.session, self.settings = session, settings or get_settings()
        self.random = random.Random(self.settings.simulation_seed)
        self.drones, self.telemetry, self.events = (
            DroneService(session),
            TelemetryService(session),
            EventService(session),
        )

    def initialize_fleet(self) -> list:
        fleet = []
        for index in range(1, self.settings.simulation_drone_count + 1):
            drone_id = f"DR-{index:02d}"
            try:
                fleet.append(self.drones.get(drone_id))
                continue
            except Exception:
                pass
            offset = index * 0.001
            fleet.append(
                self.drones.register(
                    DroneCreate(
                        drone_id=drone_id,
                        name=f"Simulation Drone {index}",
                        latitude=self.settings.simulation_latitude + offset,
                        longitude=self.settings.simulation_longitude - offset,
                        altitude=45 + index,
                        current_speed=0,
                        battery_percentage=95 - index * 3,
                        temperature=24,
                        gps_accuracy=1.5,
                        health_status=HealthStatus.HEALTHY,
                    )
                )
            )
        return fleet

    def generate_telemetry(self, drone_id: str) -> object:
        drone = self.drones.get(drone_id)
        if drone.status == DroneStatus.OFFLINE:
            raise SimulationError("Cannot generate telemetry for offline drone")
        return self.telemetry.record(
            TelemetryCreate(
                drone_id=drone_id,
                latitude=drone.latitude + self.random.uniform(-0.0002, 0.0002),
                longitude=drone.longitude + self.random.uniform(-0.0002, 0.0002),
                altitude=max(0, drone.altitude + self.random.uniform(-2, 2)),
                speed=max(0, drone.current_speed + self.random.uniform(0, 4)),
                battery_percentage=max(0, drone.battery_percentage - self.random.uniform(0.1, 0.8)),
                temperature=drone.temperature + self.random.uniform(-0.5, 0.5),
                gps_accuracy=max(0.5, drone.gps_accuracy + self.random.uniform(-0.2, 0.4)),
                health_status=drone.health_status,
            )
        )

    def generate_event(self, scenario: EventType, drone_id: str | None = None) -> object:
        for _ in range(100):
            event_id = f"SIM-{scenario.value}-{self.random.randint(1000, 9999)}"
            if self.events.repo.get_by_id(event_id) is None:
                break
        else:
            raise RuntimeError("unable to generate a unique simulation event ID")

        drone = self.drones.get(drone_id) if drone_id else None
        metadata = {
            "simulated": True,
            "scenario": scenario.value,
            "zone": "ZONE_B",
            "camera_confidence": 0.91,
        }
        return self.events.create(
            EventCreate(
                event_id=event_id,
                event_type=scenario,
                severity=Severity.HIGH
                if scenario != EventType.BATTERY_WARNING
                else Severity.MEDIUM,
                confidence=0.91,
                description=f"Simulated {scenario.value.lower()} event; not real perception.",
                drone_id=drone_id,
                latitude=drone.latitude if drone else None,
                longitude=drone.longitude if drone else None,
                metadata=metadata,
            )
        )
