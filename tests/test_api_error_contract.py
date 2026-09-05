from __future__ import annotations

from fastapi import APIRouter, HTTPException
from fastapi.testclient import TestClient
from sqlalchemy.exc import SQLAlchemyError

from aeromind.core.exceptions import (
    DroneNotFound,
    InvalidDroneState,
    InvalidTelemetry,
)
from aeromind.main import create_app


def _client_with_test_routes() -> TestClient:
    app = create_app()
    router = APIRouter(prefix="/_test/errors")

    @router.get("/domain/not-found")
    def domain_not_found() -> None:
        raise DroneNotFound("Drone test-404 was not found.")

    @router.get("/domain/conflict")
    def domain_conflict() -> None:
        raise InvalidDroneState("Drone cannot perform this operation.")

    @router.get("/domain/validation")
    def domain_validation() -> None:
        raise InvalidTelemetry("Telemetry values are invalid.")

    @router.get("/http")
    def http_error() -> None:
        raise HTTPException(status_code=404, detail="Test resource not found.")

    @router.get("/database")
    def database_error() -> None:
        raise SQLAlchemyError("sensitive database details")

    @router.get("/unexpected")
    def unexpected_error() -> None:
        raise RuntimeError("sensitive internal details")

    app.include_router(router)
    return TestClient(app, raise_server_exceptions=False)


def test_domain_not_found_uses_shared_error_envelope() -> None:
    response = _client_with_test_routes().get("/_test/errors/domain/not-found")

    assert response.status_code == 404
    assert response.json() == {
        "code": "DRONE_NOT_FOUND",
        "message": "Drone test-404 was not found.",
        "details": [],
    }


def test_domain_conflict_uses_shared_error_envelope() -> None:
    response = _client_with_test_routes().get("/_test/errors/domain/conflict")

    assert response.status_code == 409
    assert response.json() == {
        "code": "INVALID_DRONE_STATE",
        "message": "Drone cannot perform this operation.",
        "details": [],
    }


def test_domain_validation_uses_shared_error_envelope() -> None:
    response = _client_with_test_routes().get("/_test/errors/domain/validation")

    assert response.status_code == 422
    assert response.json() == {
        "code": "INVALID_TELEMETRY",
        "message": "Telemetry values are invalid.",
        "details": [],
    }


def test_http_exception_is_normalized() -> None:
    response = _client_with_test_routes().get("/_test/errors/http")

    assert response.status_code == 404
    assert response.json() == {
        "code": "NOT_FOUND",
        "message": "Test resource not found.",
        "details": [],
    }


def test_unexpected_exception_is_sanitized() -> None:
    response = _client_with_test_routes().get("/_test/errors/unexpected")

    assert response.status_code == 500
    assert response.json() == {
        "code": "INTERNAL_ERROR",
        "message": "An internal server error occurred.",
        "details": [],
    }
    assert "sensitive" not in response.text


def test_database_exception_is_sanitized() -> None:
    response = _client_with_test_routes().get("/_test/errors/database")

    assert response.status_code == 500
    assert response.json() == {
        "code": "DATABASE_ERROR",
        "message": "A database error occurred.",
        "details": [],
    }
    assert "sensitive" not in response.text


def test_request_validation_excludes_raw_input() -> None:
    app = create_app()
    client = TestClient(app)

    response = client.post(
        "/drones",
        json={
            "drone_id": "validation-test",
            "name": "Validation Test",
            "latitude": "NOT_A_NUMBER",
            "longitude": 80,
            "battery_percentage": 50,
            "temperature": 25,
            "gps_accuracy": 1,
        },
    )

    assert response.status_code == 422

    body = response.json()

    assert body["code"] == "VALIDATION_ERROR"
    assert body["message"] == "Request validation failed."
    assert body["details"]

    for issue in body["details"]:
        assert set(issue) == {"location", "type", "message"}
        assert "input" not in issue

    assert "NOT_A_NUMBER" not in response.text


def test_request_validation_has_stable_shape() -> None:
    app = create_app()
    client = TestClient(app)

    response = client.post("/drones", json={})

    assert response.status_code == 422

    body = response.json()

    assert set(body) == {"code", "message", "details"}
    assert body["code"] == "VALIDATION_ERROR"
    assert body["message"] == "Request validation failed."
    assert isinstance(body["details"], list)

    for issue in body["details"]:
        assert set(issue) == {"location", "type", "message"}
        assert isinstance(issue["location"], list)
        assert isinstance(issue["type"], str)
        assert isinstance(issue["message"], str)
