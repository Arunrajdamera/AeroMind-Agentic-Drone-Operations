from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from aeromind.core.config import Settings
from aeromind.core.exceptions import InvalidDroneState
from aeromind.db.base import Base
from aeromind.models.domain import DroneStatus, EventType, MissionType, Priority
from aeromind.repositories.domain import TelemetryRepository
from aeromind.schemas.api import DroneCreate, DroneUpdate, EventCreate, MissionCreate
from aeromind.services.domain import DroneService, EventService, MissionService
from aeromind.services.simulation import DroneSimulator


def session() -> Session:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return Session(engine)


def drone_data(drone_id: str = "DR-99") -> DroneCreate:
    return DroneCreate(
        drone_id=drone_id,
        name="Test",
        latitude=10,
        longitude=20,
        battery_percentage=90,
        temperature=24,
        gps_accuracy=1,
    )


def test_drone_mission_telemetry_and_event() -> None:
    with session() as db:
        drones, missions = DroneService(db), MissionService(db)
        drone = drones.register(drone_data())
        mission = missions.create(
            MissionCreate(
                mission_id="MS-01",
                mission_type=MissionType.PERIMETER_INSPECTION,
                priority=Priority.HIGH,
                target_latitude=10,
                target_longitude=20,
                objective="Inspect",
            )
        )
        missions.assign(mission.mission_id, drone.drone_id)
        assert mission.status.value == "ASSIGNED"
        event = EventService(db).create(
            EventCreate(
                event_id="EV-01",
                event_type=EventType.INTRUSION,
                severity=Priority.HIGH,
                confidence=0.9,
                description="simulated",
                drone_id=drone.drone_id,
                metadata={"simulated": True},
            )
        )
        assert event.drone_id == drone.id


def test_offline_drone_cannot_enter_mission() -> None:
    with session() as db:
        service = DroneService(db)
        service.register(drone_data())
        service.update("DR-99", DroneUpdate(status=DroneStatus.OFFLINE))
        try:
            service.update("DR-99", DroneUpdate(status=DroneStatus.IN_MISSION))
        except InvalidDroneState:
            pass
        else:
            raise AssertionError("invalid state transition was accepted")


def test_deterministic_fleet_and_telemetry() -> None:
    settings = Settings(database_url="sqlite://", simulation_seed=42)
    with session() as db:
        simulator = DroneSimulator(db, settings)
        fleet = simulator.initialize_fleet()
        first = simulator.generate_telemetry("DR-01")
        assert len(fleet) == 5
        assert first.battery_percentage < 92
        assert len(TelemetryRepository(db).list_for_drone(fleet[0].id)) == 1
