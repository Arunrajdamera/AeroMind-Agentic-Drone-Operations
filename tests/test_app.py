from fastapi.testclient import TestClient

from aeromind.main import create_app


def test_application_starts() -> None:
    app = create_app()
    assert app.title == "AeroMind"


def test_health_endpoint() -> None:
    with TestClient(create_app()) as client:
        response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "aeromind", "version": "0.1.0"}
