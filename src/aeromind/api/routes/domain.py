from __future__ import annotations

# ruff: noqa: B008  # FastAPI dependency declarations use Depends in signatures.
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from aeromind.core.exceptions import DomainError
from aeromind.db.session import get_session
from aeromind.repositories.domain import (
    DroneRepository,
    EventRepository,
    MissionRepository,
    TelemetryRepository,
)
from aeromind.schemas.api import (
    DroneCreate,
    DroneRead,
    DroneUpdate,
    EventCreate,
    EventRead,
    MissionCreate,
    MissionRead,
    TelemetryCreate,
    TelemetryRead,
)
from aeromind.services.domain import DroneService, EventService, MissionService, TelemetryService

router = APIRouter()


def fail(error: DomainError) -> None:
    raise HTTPException(status_code=404, detail=str(error))


def drone_view(item: object) -> DroneRead:
    return DroneRead.model_validate(item)


def mission_view(item: object) -> MissionRead:
    return MissionRead(
        mission_id=item.mission_id,
        mission_type=item.mission_type,
        priority=item.priority,
        target_latitude=item.target_latitude,
        target_longitude=item.target_longitude,
        objective=item.objective,
        status=item.status,
        assigned_drone_id=item.assigned_drone.drone_id if item.assigned_drone else None,
    )


def telemetry_view(item: object, drone_id: str) -> TelemetryRead:
    return TelemetryRead(
        drone_id=drone_id,
        latitude=item.latitude,
        longitude=item.longitude,
        altitude=item.altitude,
        speed=item.speed,
        battery_percentage=item.battery_percentage,
        temperature=item.temperature,
        gps_accuracy=item.gps_accuracy,
        health_status=item.health_status,
        timestamp=item.timestamp,
    )


def event_view(item: object, session: Session) -> EventRead:
    return EventRead(
        event_id=item.event_id,
        event_type=item.event_type,
        severity=item.severity,
        confidence=item.confidence,
        description=item.description,
        drone_id=item.drone.drone_id if item.drone else None,
        mission_id=item.mission.mission_id if item.mission else None,
        latitude=item.latitude,
        longitude=item.longitude,
        metadata=item.metadata_,
        created_at=item.created_at,
    )


@router.get("/drones", response_model=list[DroneRead])
def list_drones(session: Session = Depends(get_session)) -> list[DroneRead]:
    return [drone_view(x) for x in DroneRepository(session).list()]


@router.post("/drones", response_model=DroneRead, status_code=status.HTTP_201_CREATED)
def create_drone(data: DroneCreate, session: Session = Depends(get_session)) -> DroneRead:
    try:
        item = DroneService(session).register(data)
        session.commit()
        return drone_view(item)
    except (DomainError, ValueError) as error:
        session.rollback()
        raise HTTPException(422, str(error)) from error


@router.get("/drones/{drone_id}", response_model=DroneRead)
def get_drone(drone_id: str, session: Session = Depends(get_session)) -> DroneRead:
    try:
        return drone_view(DroneService(session).get(drone_id))
    except DomainError as error:
        fail(error)


@router.patch("/drones/{drone_id}", response_model=DroneRead)
def patch_drone(
    drone_id: str, data: DroneUpdate, session: Session = Depends(get_session)
) -> DroneRead:
    try:
        item = DroneService(session).update(drone_id, data)
        session.commit()
        return drone_view(item)
    except DomainError as error:
        session.rollback()
        fail(error)


@router.get("/drones/{drone_id}/telemetry", response_model=list[TelemetryRead])
def drone_telemetry(drone_id: str, session: Session = Depends(get_session)) -> list[TelemetryRead]:
    try:
        drone = DroneService(session).get(drone_id)
        return [
            telemetry_view(x, drone_id)
            for x in TelemetryRepository(session).list_for_drone(drone.id)
        ]
    except DomainError as error:
        fail(error)


@router.get("/missions", response_model=list[MissionRead])
def list_missions(session: Session = Depends(get_session)) -> list[MissionRead]:
    return [mission_view(x) for x in MissionRepository(session).list()]


@router.post("/missions", response_model=MissionRead, status_code=201)
def create_mission(data: MissionCreate, session: Session = Depends(get_session)) -> MissionRead:
    try:
        item = MissionService(session).create(data)
        session.commit()
        return mission_view(item)
    except ValueError as error:
        session.rollback()
        raise HTTPException(422, str(error)) from error


@router.get("/missions/{mission_id}", response_model=MissionRead)
def get_mission(mission_id: str, session: Session = Depends(get_session)) -> MissionRead:
    try:
        return mission_view(MissionService(session).get(mission_id))
    except DomainError as error:
        fail(error)


@router.post("/telemetry", response_model=TelemetryRead, status_code=201)
def create_telemetry(
    data: TelemetryCreate, session: Session = Depends(get_session)
) -> TelemetryRead:
    try:
        item = TelemetryService(session).record(data)
        session.commit()
        return telemetry_view(item, data.drone_id)
    except DomainError as error:
        session.rollback()
        fail(error)


@router.get("/events", response_model=list[EventRead])
def list_events(session: Session = Depends(get_session)) -> list[EventRead]:
    return [event_view(x, session) for x in EventRepository(session).list()]


@router.post("/events", response_model=EventRead, status_code=201)
def create_event(data: EventCreate, session: Session = Depends(get_session)) -> EventRead:
    try:
        item = EventService(session).create(data)
        session.commit()
        return event_view(item, session)
    except (DomainError, ValueError) as error:
        session.rollback()
        raise HTTPException(422, str(error)) from error


@router.get("/events/{event_id}", response_model=EventRead)
def get_event(event_id: str, session: Session = Depends(get_session)) -> EventRead:
    item = EventRepository(session).get_by_id(event_id)
    if not item:
        raise HTTPException(404, "Event not found")
    return event_view(item, session)
