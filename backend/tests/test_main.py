from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health_endpoint_returns_ok_payload() -> None:
    response = client.get("/api/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "pm-backend"}


def test_root_serves_hello_world_page() -> None:
    response = client.get("/")

    assert response.status_code == 200
    assert "Hello world from the backend scaffold" in response.text
    assert "/api/health" in response.text
