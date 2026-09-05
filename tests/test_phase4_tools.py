from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from aeromind.db.base import Base
from aeromind.schemas.api import DroneCreate
from aeromind.services.domain import DroneService
from aeromind.tools.catalog import build_catalog
from aeromind.tools.definitions import ToolCall, ToolRisk, ToolStatus
from aeromind.tools.executor import ToolExecutor


def make_session() -> Session:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return Session(engine)


def test_catalog_is_authoritative_executor_path() -> None:
    with make_session() as session:
        DroneService(session).register(
            DroneCreate(
                drone_id="DR-42",
                name="Catalog Test",
                latitude=1,
                longitude=2,
                battery_percentage=80,
                temperature=20,
                gps_accuracy=1,
            )
        )
        catalog = build_catalog(session)
        definition = catalog.get("get_drone_status")
        assert definition is not None and definition.risk == ToolRisk.LOW
        result = ToolExecutor(session, catalog=catalog).execute(
            ToolCall(name="get_drone_status", arguments={"drone_id": "DR-42"}, request_id="test")
        )
        assert result.status == ToolStatus.SUCCEEDED
        assert result.result["drone_id"] == "DR-42"


def test_catalog_has_all_phase4_tools_and_high_risk_is_gated() -> None:
    with make_session() as session:
        catalog = build_catalog(session)
        assert len(catalog.list_tools()) == 12
        result = ToolExecutor(session, catalog=catalog).execute(
            ToolCall(name="return_to_home", arguments={"drone_id": "DR-01"}, request_id="test")
        )
        assert result.status == ToolStatus.REQUIRES_APPROVAL


def test_catalog_unknown_and_invalid_calls_fail_closed() -> None:
    with make_session() as session:
        executor = ToolExecutor(session, catalog=build_catalog(session))
        unknown = executor.execute(ToolCall(name="shell_command", arguments={}, request_id="test"))
        invalid = executor.execute(
            ToolCall(name="get_drone_status", arguments={}, request_id="test")
        )
        assert unknown.status == ToolStatus.BLOCKED
        assert invalid.status == ToolStatus.FAILED
