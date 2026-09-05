from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from aeromind.models.domain import Drone, Event, Mission, Telemetry


class DroneRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def create(self, drone: Drone) -> Drone:
        self.session.add(drone)
        self.session.flush()
        return drone

    def get_by_id(self, id_: UUID) -> Drone | None:
        return self.session.get(Drone, id_)

    def get_by_drone_id(self, drone_id: str) -> Drone | None:
        return self.session.scalar(select(Drone).where(Drone.drone_id == drone_id))

    def list(self) -> list[Drone]:
        return list(self.session.scalars(select(Drone).order_by(Drone.drone_id)))

    def update(self, drone: Drone) -> Drone:
        self.session.flush()
        return drone

    def delete(self, drone: Drone) -> None:
        self.session.delete(drone)
        self.session.flush()


class MissionRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def create(self, mission: Mission) -> Mission:
        self.session.add(mission)
        self.session.flush()
        return mission

    def get_by_id(self, id_: UUID) -> Mission | None:
        return self.session.get(Mission, id_)

    def get_by_mission_id(self, mission_id: str) -> Mission | None:
        return self.session.scalar(select(Mission).where(Mission.mission_id == mission_id))

    def list(self) -> list[Mission]:
        return list(self.session.scalars(select(Mission).order_by(Mission.created_at.desc())))

    def update(self, mission: Mission) -> Mission:
        self.session.flush()
        return mission


class TelemetryRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def create(self, telemetry: Telemetry) -> Telemetry:
        self.session.add(telemetry)
        self.session.flush()
        return telemetry

    def list_recent(self, limit: int = 100) -> list[Telemetry]:
        return list(
            self.session.scalars(
                select(Telemetry).order_by(Telemetry.timestamp.desc()).limit(limit)
            )
        )

    def list_for_drone(self, drone_id: UUID, limit: int = 100) -> list[Telemetry]:
        return list(
            self.session.scalars(
                select(Telemetry)
                .where(Telemetry.drone_id == drone_id)
                .order_by(Telemetry.timestamp.desc())
                .limit(limit)
            )
        )


class EventRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def create(self, event: Event) -> Event:
        self.session.add(event)
        self.session.flush()
        return event

    def get_by_id(self, event_id: str) -> Event | None:
        return self.session.scalar(select(Event).where(Event.event_id == event_id))

    def list(self) -> list[Event]:
        return list(self.session.scalars(select(Event).order_by(Event.created_at.desc())))

    def list_for_drone(self, drone_id: UUID) -> list[Event]:
        return list(self.session.scalars(select(Event).where(Event.drone_id == drone_id)))

    def list_for_mission(self, mission_id: UUID) -> list[Event]:
        return list(self.session.scalars(select(Event).where(Event.mission_id == mission_id)))
