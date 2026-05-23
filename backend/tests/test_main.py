from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health_endpoint_returns_ok_payload() -> None:
    response = client.get("/api/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "pm-backend"}


def test_root_serves_frontend_static_page() -> None:
    response = client.get("/")

    assert response.status_code == 200
    assert "Kanban Studio" in response.text
    assert "/api/health" in response.text
