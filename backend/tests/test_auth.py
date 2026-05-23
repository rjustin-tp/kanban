from fastapi.testclient import TestClient

from app.main import app, sessions

client = TestClient(app)


def test_login_rejects_invalid_credentials() -> None:
    sessions.clear()
    response = client.post(
        "/api/auth/login",
        json={"username": "user", "password": "wrong"},
    )

    assert response.status_code == 401
    assert response.json() == {"detail": "Invalid credentials"}


def test_login_creates_session_and_allows_session_check() -> None:
    sessions.clear()
    response = client.post(
        "/api/auth/login",
        json={"username": "user", "password": "password"},
    )

    assert response.status_code == 200
    assert response.json() == {"ok": True, "user": "user"}
    assert "pm_session" in response.cookies

    session_check = client.get("/api/auth/session")
    assert session_check.status_code == 200
    assert session_check.json() == {"authenticated": True, "user": "user"}


def test_logout_clears_session_and_blocks_protected_route() -> None:
    sessions.clear()
    login_response = client.post(
        "/api/auth/login",
        json={"username": "user", "password": "password"},
    )
    assert login_response.status_code == 200

    logout_response = client.post("/api/auth/logout")
    assert logout_response.status_code == 200
    assert logout_response.json() == {"ok": True}

    protected_response = client.get("/api/auth/session")
    assert protected_response.status_code == 401
    assert protected_response.json() == {"detail": "Not authenticated"}
