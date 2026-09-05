# ruff: noqa: B008  # FastAPI dependency declarations use Depends in signatures.

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from aeromind.core.exceptions import DomainError
from aeromind.db.base import Base
from aeromind.db.session import engine, get_session
from aeromind.models.domain import EventType
from aeromind.services.simulation import DroneSimulator

router = APIRouter(prefix="/simulation", tags=["simulation-only"])


class EventRequest(BaseModel):
    scenario: EventType
    drone_id: str | None = None


class TelemetryRequest(BaseModel):
    drone_id: str


@router.post("/initialize")
def initialize(session: Session = Depends(get_session)) -> dict[str, object]:
    try:
        drones = DroneSimulator(session).initialize_fleet()
        session.commit()
        return {"simulation_only": True, "drones": [drone.drone_id for drone in drones]}
    except DomainError as error:
        session.rollback()
        raise HTTPException(422, str(error)) from error


@router.post("/telemetry")
def telemetry(data: TelemetryRequest, session: Session = Depends(get_session)) -> dict[str, object]:
    try:
        result = DroneSimulator(session).generate_telemetry(data.drone_id)
        session.commit()
        return {"simulation_only": True, "telemetry_id": str(result.id)}
    except DomainError as error:
        session.rollback()
        raise HTTPException(422, str(error)) from error


@router.post("/event")
def event(data: EventRequest, session: Session = Depends(get_session)) -> dict[str, object]:
    try:
        result = DroneSimulator(session).generate_event(data.scenario, data.drone_id)
        session.commit()
        return {"simulation_only": True, "event_id": result.event_id}
    except DomainError as error:
        session.rollback()
        raise HTTPException(422, str(error)) from error


@router.post("/reset")
def reset() -> dict[str, bool]:
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    return {"simulation_only": True, "reset": True}
