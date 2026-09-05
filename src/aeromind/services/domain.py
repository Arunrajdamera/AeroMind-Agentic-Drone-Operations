from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy.orm import Session

from aeromind.core.exceptions import (
    DroneNotFound,
    InvalidDroneState,
    InvalidMissionState,
    MissionNotFound,
)
from aeromind.models.domain import Drone, DroneStatus, Event, Mission, MissionStatus, Telemetry
from aeromind.repositories.domain import (
    DroneRepository,
    EventRepository,
    MissionRepository,
    TelemetryRepository,
)
from aeromind.schemas.api import (
    DroneCreate,
    DroneUpdate,
    EventCreate,
    MissionCreate,
    TelemetryCreate,
    TelemetryHealth,
)


class DroneService:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.repo = DroneRepository(session)

    def register(self, data: DroneCreate) -> Drone:
        if self.repo.get_by_drone_id(data.drone_id):
            raise ValueError("drone_id already exists")
        return self.repo.create(Drone(**data.model_dump()))

    def get(self, drone_id: str) -> Drone:
        drone = self.repo.get_by_drone_id(drone_id)
        if not drone:
            raise DroneNotFound(f"Drone {drone_id} was not found")
        return drone

    def update(self, drone_id: str, data: DroneUpdate) -> Drone:
        drone = self.get(drone_id)
        if (
            data.status
            and drone.status == DroneStatus.OFFLINE
            and data.status == DroneStatus.IN_MISSION
        ):
            raise InvalidDroneState("Offline drone cannot enter a mission")
        for field, value in data.model_dump(exclude_none=True).items():
            setattr(drone, field, value)
        return self.repo.update(drone)

    def change_status(self, drone_id: str, status: DroneStatus) -> Drone:
        return self.update(drone_id, DroneUpdate(status=status))


class MissionService:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.repo = MissionRepository(session)
        self.drones = DroneService(session)

    def create(self, data: MissionCreate) -> Mission:
        if self.repo.get_by_mission_id(data.mission_id):
            raise ValueError("mission_id already exists")
        return self.repo.create(Mission(**data.model_dump()))

    def get(self, mission_id: str) -> Mission:
        mission = self.repo.get_by_mission_id(mission_id)
        if not mission:
            raise MissionNotFound(f"Mission {mission_id} was not found")
        return mission

    def assign(self, mission_id: str, drone_id: str) -> Mission:
        mission, drone = self.get(mission_id), self.drones.get(drone_id)
        if mission.status != MissionStatus.PLANNED:
            raise InvalidMissionState("Only planned missions can be assigned")
        if drone.status != DroneStatus.AVAILABLE:
            raise InvalidDroneState("Drone is not available for assignment")
        mission.assigned_drone_id, mission.status, drone.mission_id, drone.status = (
            drone.id,
            MissionStatus.ASSIGNED,
            mission.id,
            DroneStatus.DEPLOYED,
        )
        self.session.flush()
        return mission

    def start(self, mission_id: str) -> Mission:
        mission = self.get(mission_id)
        if mission.status != MissionStatus.ASSIGNED or not mission.assigned_drone:
            raise InvalidMissionState("Assigned drone required before start")
        mission.status, mission.started_at, mission.assigned_drone.status = (
            MissionStatus.IN_PROGRESS,
            datetime.now(UTC),
            DroneStatus.IN_MISSION,
        )
        self.session.flush()
        return mission

    def complete(self, mission_id: str, aborted: bool = False) -> Mission:
        mission = self.get(mission_id)
        if mission.status not in {MissionStatus.IN_PROGRESS, MissionStatus.PAUSED}:
            raise InvalidMissionState("Mission is not active")
        mission.status, mission.completed_at = (
            (MissionStatus.ABORTED if aborted else MissionStatus.COMPLETED),
            datetime.now(UTC),
        )
        if mission.assigned_drone:
            mission.assigned_drone.status, mission.assigned_drone.mission_id = (
                DroneStatus.RETURNING,
                None,
            )
        self.session.flush()
        return mission


class TelemetryService:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.repo = TelemetryRepository(session)
        self.drones = DroneService(session)

    def record(self, data: TelemetryCreate) -> Telemetry:
        drone = self.drones.get(data.drone_id)
        fields = data.model_dump(exclude={"drone_id"})
        telemetry = self.repo.create(Telemetry(drone_id=drone.id, **fields))
        for key in (
            "latitude",
            "longitude",
            "altitude",
            "battery_percentage",
            "temperature",
            "gps_accuracy",
            "health_status",
        ):
            setattr(drone, key, fields[key])
        drone.current_speed, drone.last_seen = fields["speed"], datetime.now(UTC)
        self.session.flush()
        return telemetry

    def health(self, drone_id: str) -> TelemetryHealth:
        drone = self.drones.get(drone_id)
        warnings: list[str] = []
        if datetime.now(UTC) - drone.last_seen.replace(tzinfo=UTC) > timedelta(minutes=5):
            warnings.append("Telemetry stale")
        if drone.gps_accuracy > 15:
            warnings.append("GPS accuracy degraded")
        if drone.battery_percentage < 15 or drone.battery_percentage > 100:
            warnings.append("Abnormal battery")
        if not -90 <= drone.latitude <= 90 or not -180 <= drone.longitude <= 180:
            warnings.append("Invalid coordinates")
        if not -20 <= drone.temperature <= 80:
            warnings.append("Abnormal temperature")
        return TelemetryHealth(healthy=not warnings, warnings=warnings)


class EventService:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.repo = EventRepository(session)
        self.drones = DroneService(session)
        self.missions = MissionService(session)

    def create(self, data: EventCreate) -> Event:
        values = data.model_dump()
        drone_id, mission_id = values.pop("drone_id"), values.pop("mission_id")
        values["metadata_"] = values.pop("metadata")
        if drone_id:
            values["drone_id"] = self.drones.get(drone_id).id
        if mission_id:
            values["mission_id"] = self.missions.get(mission_id).id
        if self.repo.get_by_id(values["event_id"]):
            raise ValueError("event_id already exists")
        return self.repo.create(Event(**values))
