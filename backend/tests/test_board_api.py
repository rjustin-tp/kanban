from fastapi.testclient import TestClient

from app.board_repository import BoardRepository
from app import main as main_module


def _login(client: TestClient) -> None:
    response = client.post(
        "/api/auth/login",
        json={"username": "user", "password": "password"},
    )
    assert response.status_code == 200


def test_board_routes_require_authentication(tmp_path) -> None:
    original_repo = main_module.board_repo
    main_module.board_repo = BoardRepository(tmp_path / "kanban.db")
    main_module.board_repo.initialize()
    main_module.sessions.clear()

    try:
        with TestClient(main_module.app) as client:
            response = client.get("/api/board")
            assert response.status_code == 401
            assert response.json() == {"detail": "Not authenticated"}
    finally:
        main_module.board_repo = original_repo
        main_module.sessions.clear()


def test_get_board_seeds_data_for_authenticated_user(tmp_path) -> None:
    original_repo = main_module.board_repo
    main_module.board_repo = BoardRepository(tmp_path / "kanban.db")
    main_module.board_repo.initialize()
    main_module.sessions.clear()

    try:
        with TestClient(main_module.app) as client:
            _login(client)
            response = client.get("/api/board")
            assert response.status_code == 200
            body = response.json()
            assert len(body["columns"]) == 5
            assert body["columns"][0]["id"] == "col-backlog"
            assert "card-1" in body["cards"]
    finally:
        main_module.board_repo = original_repo
        main_module.sessions.clear()


def test_put_board_persists_updates(tmp_path) -> None:
    original_repo = main_module.board_repo
    main_module.board_repo = BoardRepository(tmp_path / "kanban.db")
    main_module.board_repo.initialize()
    main_module.sessions.clear()

    try:
        with TestClient(main_module.app) as client:
            _login(client)
            board = client.get("/api/board").json()
            board["columns"][0]["title"] = "Queue"

            put_response = client.put("/api/board", json=board)
            assert put_response.status_code == 200
            assert put_response.json()["columns"][0]["title"] == "Queue"

            reload_response = client.get("/api/board")
            assert reload_response.status_code == 200
            assert reload_response.json()["columns"][0]["title"] == "Queue"
    finally:
        main_module.board_repo = original_repo
        main_module.sessions.clear()


def test_put_board_rejects_invalid_payload(tmp_path) -> None:
    original_repo = main_module.board_repo
    main_module.board_repo = BoardRepository(tmp_path / "kanban.db")
    main_module.board_repo.initialize()
    main_module.sessions.clear()

    try:
        with TestClient(main_module.app) as client:
            _login(client)
            board = client.get("/api/board").json()
            board["columns"][0]["cardIds"].append("missing-card")

            response = client.put("/api/board", json=board)
            assert response.status_code == 400
            assert response.json() == {
                "detail": "All card ids must exist in cards map."
            }
    finally:
        main_module.board_repo = original_repo
        main_module.sessions.clear()
