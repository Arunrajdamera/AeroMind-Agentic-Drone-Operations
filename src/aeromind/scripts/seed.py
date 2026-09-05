from alembic import command
from alembic.config import Config

from aeromind.db.session import SessionLocal
from aeromind.services.simulation import DroneSimulator


def main() -> None:
    command.upgrade(Config("alembic.ini"), "head")
    with SessionLocal.begin() as session:
        drones = DroneSimulator(session).initialize_fleet()
    print(f"Seeded {len(drones)} simulated drones.")


if __name__ == "__main__":
    main()
