from fastapi.testclient import TestClient

from app.board_repository import BoardRepository
from app import main as main_module
from app.ai_service import OpenRouterConfigError, OpenRouterRequestError, OpenRouterTimeoutError


def _login(client: TestClient) -> None:
    response = client.post(
        "/api/auth/login",
        json={"username": "user", "password": "password"},
    )
    assert response.status_code == 200


def test_ai_smoke_requires_authentication() -> None:
    with TestClient(main_module.app) as client:
        response = client.get("/api/ai/smoke")
        assert response.status_code == 401
        assert response.json() == {"detail": "Not authenticated"}


def test_ai_smoke_returns_prompt_response() -> None:
    original_client = main_module.ai_client

    class StubClient:
        def prompt_text(self, prompt: str) -> str:
            assert prompt == "2+2"
            return "4"

    main_module.ai_client = StubClient()
    main_module.sessions.clear()
    try:
        with TestClient(main_module.app) as client:
            _login(client)
            response = client.get("/api/ai/smoke")
            assert response.status_code == 200
            assert response.json() == {"prompt": "2+2", "response": "4"}
    finally:
        main_module.ai_client = original_client
        main_module.sessions.clear()


def test_ai_smoke_handles_missing_api_key() -> None:
    original_client = main_module.ai_client

    class StubClient:
        def prompt_text(self, _prompt: str) -> str:
            raise OpenRouterConfigError("Missing OPENROUTER_API_KEY.")

    main_module.ai_client = StubClient()
    main_module.sessions.clear()
    try:
        with TestClient(main_module.app) as client:
            _login(client)
            response = client.get("/api/ai/smoke")
            assert response.status_code == 500
            assert response.json() == {"detail": "Missing OPENROUTER_API_KEY."}
    finally:
        main_module.ai_client = original_client
        main_module.sessions.clear()


def test_ai_smoke_handles_upstream_error() -> None:
    original_client = main_module.ai_client

    class StubClient:
        def prompt_text(self, _prompt: str) -> str:
            raise OpenRouterRequestError("OpenRouter request failed with status 503.")

    main_module.ai_client = StubClient()
    main_module.sessions.clear()
    try:
        with TestClient(main_module.app) as client:
            _login(client)
            response = client.get("/api/ai/smoke")
            assert response.status_code == 502
            assert response.json() == {
                "detail": "OpenRouter request failed with status 503."
            }
    finally:
        main_module.ai_client = original_client
        main_module.sessions.clear()


def test_ai_smoke_handles_timeout() -> None:
    original_client = main_module.ai_client

    class StubClient:
        def prompt_text(self, _prompt: str) -> str:
            raise OpenRouterTimeoutError("OpenRouter request timed out.")

    main_module.ai_client = StubClient()
    main_module.sessions.clear()
    try:
        with TestClient(main_module.app) as client:
            _login(client)
            response = client.get("/api/ai/smoke")
            assert response.status_code == 504
            assert response.json() == {"detail": "OpenRouter request timed out."}
    finally:
        main_module.ai_client = original_client
        main_module.sessions.clear()


def test_ai_chat_requires_authentication() -> None:
    with TestClient(main_module.app) as client:
        response = client.post("/api/ai/chat", json={"message": "hello"})
        assert response.status_code == 401
        assert response.json() == {"detail": "Not authenticated"}


def test_ai_chat_returns_reply_without_board_update(tmp_path) -> None:
    original_client = main_module.ai_client
    original_repo = main_module.board_repo

    class StubClient:
        def prompt_structured_chat(
            self, board: dict, user_message: str, conversation: list[dict[str, str]]
        ) -> dict:
            assert user_message == "Give me a status update."
            assert isinstance(board.get("columns"), list)
            assert conversation[-1] == {"role": "user", "content": "Give me a status update."}
            return {"assistantMessage": "Everything looks good."}

    main_module.ai_client = StubClient()
    main_module.board_repo = BoardRepository(tmp_path / "kanban.db")
    main_module.board_repo.initialize()
    main_module.sessions.clear()
    main_module.chat_histories.clear()
    try:
        with TestClient(main_module.app) as client:
            _login(client)
            response = client.post("/api/ai/chat", json={"message": "Give me a status update."})
            assert response.status_code == 200
            assert response.json()["assistantMessage"] == "Everything looks good."
            assert response.json()["appliedOperations"] is False
    finally:
        main_module.ai_client = original_client
        main_module.board_repo = original_repo
        main_module.sessions.clear()
        main_module.chat_histories.clear()


def test_ai_chat_applies_valid_board_operations(tmp_path) -> None:
    original_client = main_module.ai_client
    original_repo = main_module.board_repo

    class StubClient:
        def prompt_structured_chat(
            self, board: dict, _user_message: str, _conversation: list[dict[str, str]]
        ) -> dict:
            source_column = next(col for col in board["columns"] if col["cardIds"])
            source_card = source_column["cardIds"][0]
            target_column = next(col for col in board["columns"] if col["id"] != source_column["id"])
            return {
                "assistantMessage": "Moved one card.",
                "operations": [
                    {
                        "type": "move_card",
                        "cardId": source_card,
                        "toColumnId": target_column["id"],
                        "toIndex": 0,
                    }
                ],
            }

    main_module.ai_client = StubClient()
    main_module.board_repo = BoardRepository(tmp_path / "kanban.db")
    main_module.board_repo.initialize()
    main_module.sessions.clear()
    main_module.chat_histories.clear()
    try:
        with TestClient(main_module.app) as client:
            _login(client)
            before_board = client.get("/api/board").json()
            moved_card = next(col["cardIds"][0] for col in before_board["columns"] if col["cardIds"])

            response = client.post("/api/ai/chat", json={"message": "Move a card."})
            assert response.status_code == 200
            assert response.json()["appliedOperations"] is True

            updated_board = response.json()["board"]
            placements = [
                col["id"] for col in updated_board["columns"] if moved_card in col["cardIds"]
            ]
            assert len(placements) == 1

            persisted_board = client.get("/api/board").json()
            persisted_placements = [
                col["id"] for col in persisted_board["columns"] if moved_card in col["cardIds"]
            ]
            assert persisted_placements == placements
    finally:
        main_module.ai_client = original_client
        main_module.board_repo = original_repo
        main_module.sessions.clear()
        main_module.chat_histories.clear()


def test_ai_chat_rejects_invalid_ai_payload_without_mutation(tmp_path) -> None:
    original_client = main_module.ai_client
    original_repo = main_module.board_repo

    class StubClient:
        def prompt_structured_chat(
            self, _board: dict, _user_message: str, _conversation: list[dict[str, str]]
        ) -> dict:
            return {"operations": [{"type": "move_card"}]}

    main_module.ai_client = StubClient()
    main_module.board_repo = BoardRepository(tmp_path / "kanban.db")
    main_module.board_repo.initialize()
    main_module.sessions.clear()
    main_module.chat_histories.clear()
    try:
        with TestClient(main_module.app) as client:
            _login(client)
            before_board = client.get("/api/board").json()
            response = client.post("/api/ai/chat", json={"message": "Do something."})
            assert response.status_code == 502
            assert response.json() == {"detail": "Invalid structured AI response."}
            after_board = client.get("/api/board").json()
            assert after_board == before_board
    finally:
        main_module.ai_client = original_client
        main_module.board_repo = original_repo
        main_module.sessions.clear()
        main_module.chat_histories.clear()


def test_ai_chat_accepts_camel_case_operation_aliases(tmp_path) -> None:
    original_client = main_module.ai_client
    original_repo = main_module.board_repo

    class StubClient:
        def prompt_structured_chat(
            self, _board: dict, _user_message: str, _conversation: list[dict[str, str]]
        ) -> dict:
            return {
                "assistantMessage": "Renamed column.",
                "operations": [
                    {
                        "type": "renameColumn",
                        "columnId": "col-backlog",
                        "newTitle": "Queue",
                    }
                ],
            }

    main_module.ai_client = StubClient()
    main_module.board_repo = BoardRepository(tmp_path / "kanban.db")
    main_module.board_repo.initialize()
    main_module.sessions.clear()
    main_module.chat_histories.clear()
    try:
        with TestClient(main_module.app) as client:
            _login(client)
            response = client.post("/api/ai/chat", json={"message": "Rename backlog"})
            assert response.status_code == 200
            assert response.json()["appliedOperations"] is True
            assert response.json()["board"]["columns"][0]["title"] == "Queue"
    finally:
        main_module.ai_client = original_client
        main_module.board_repo = original_repo
        main_module.sessions.clear()
        main_module.chat_histories.clear()


def test_ai_chat_accepts_move_card_without_to_index(tmp_path) -> None:
    original_client = main_module.ai_client
    original_repo = main_module.board_repo

    class StubClient:
        def prompt_structured_chat(
            self, _board: dict, _user_message: str, _conversation: list[dict[str, str]]
        ) -> dict:
            return {
                "assistantMessage": "Moved card.",
                "operations": [
                    {
                        "type": "moveCard",
                        "cardId": "card-2",
                        "fromColumnId": "col-backlog",
                        "toColumnId": "col-done",
                    }
                ],
            }

    main_module.ai_client = StubClient()
    main_module.board_repo = BoardRepository(tmp_path / "kanban.db")
    main_module.board_repo.initialize()
    main_module.sessions.clear()
    main_module.chat_histories.clear()
    try:
        with TestClient(main_module.app) as client:
            _login(client)
            response = client.post("/api/ai/chat", json={"message": "Move card"})
            assert response.status_code == 200
            assert response.json()["appliedOperations"] is True
            done = next(
                column
                for column in response.json()["board"]["columns"]
                if column["id"] == "col-done"
            )
            assert "card-2" in done["cardIds"]
    finally:
        main_module.ai_client = original_client
        main_module.board_repo = original_repo
        main_module.sessions.clear()
        main_module.chat_histories.clear()


def test_ai_chat_treats_null_operations_as_reply_only(tmp_path) -> None:
    original_client = main_module.ai_client
    original_repo = main_module.board_repo

    class StubClient:
        def prompt_structured_chat(
            self, _board: dict, _user_message: str, _conversation: list[dict[str, str]]
        ) -> dict:
            return {
                "assistantMessage": "Board summary.",
                "operations": None,
            }

    main_module.ai_client = StubClient()
    main_module.board_repo = BoardRepository(tmp_path / "kanban.db")
    main_module.board_repo.initialize()
    main_module.sessions.clear()
    main_module.chat_histories.clear()
    try:
        with TestClient(main_module.app) as client:
            _login(client)
            response = client.post("/api/ai/chat", json={"message": "What changed today?"})
            assert response.status_code == 200
            assert response.json()["assistantMessage"] == "Board summary."
            assert response.json()["appliedOperations"] is False
    finally:
        main_module.ai_client = original_client
        main_module.board_repo = original_repo
        main_module.sessions.clear()
        main_module.chat_histories.clear()


def test_ai_chat_summary_uses_local_complete_response(tmp_path) -> None:
    original_client = main_module.ai_client
    original_repo = main_module.board_repo

    class StubClient:
        def prompt_structured_chat(
            self, _board: dict, _user_message: str, _conversation: list[dict[str, str]]
        ) -> dict:
            raise AssertionError("Summary path should not call AI client.")

    main_module.ai_client = StubClient()
    main_module.board_repo = BoardRepository(tmp_path / "kanban.db")
    main_module.board_repo.initialize()
    main_module.sessions.clear()
    main_module.chat_histories.clear()
    try:
        with TestClient(main_module.app) as client:
            _login(client)
            response = client.post("/api/ai/chat", json={"message": "summarize my board"})
            assert response.status_code == 200
            body = response.json()
            assert body["appliedOperations"] is False
            assert "Queue" in body["assistantMessage"] or "Backlog" in body["assistantMessage"]
            assert "Gather customer signals" in body["assistantMessage"]
            assert "Done" in body["assistantMessage"]
    finally:
        main_module.ai_client = original_client
        main_module.board_repo = original_repo
        main_module.sessions.clear()
        main_module.chat_histories.clear()


def test_ai_chat_accepts_title_based_move_operation(tmp_path) -> None:
    original_client = main_module.ai_client
    original_repo = main_module.board_repo

    class StubClient:
        def prompt_structured_chat(
            self, _board: dict, _user_message: str, _conversation: list[dict[str, str]]
        ) -> dict:
            return {
                "assistantMessage": "Moved by title.",
                "operations": [
                    {
                        "type": "moveCard",
                        "cardTitle": "Gather customer signals",
                        "toColumn": "done",
                    }
                ],
            }

    main_module.ai_client = StubClient()
    main_module.board_repo = BoardRepository(tmp_path / "kanban.db")
    main_module.board_repo.initialize()
    main_module.sessions.clear()
    main_module.chat_histories.clear()
    try:
        with TestClient(main_module.app) as client:
            _login(client)
            response = client.post("/api/ai/chat", json={"message": "Move by title"})
            assert response.status_code == 200
            assert response.json()["appliedOperations"] is True
            done_column = next(
                column
                for column in response.json()["board"]["columns"]
                if column["id"] == "col-done"
            )
            assert "card-2" in done_column["cardIds"]
    finally:
        main_module.ai_client = original_client
        main_module.board_repo = original_repo
        main_module.sessions.clear()
        main_module.chat_histories.clear()


def test_ai_chat_accepts_action_style_move_operations(tmp_path) -> None:
    original_client = main_module.ai_client
    original_repo = main_module.board_repo

    class StubClient:
        def prompt_structured_chat(
            self, _board: dict, _user_message: str, _conversation: list[dict[str, str]]
        ) -> dict:
            return {
                "assistantMessage": "Moved by actions.",
                "operations": [
                    {"action": "removeCardFromColumn", "columnId": "col-backlog", "cardId": "card-2"},
                    {
                        "action": "addCardToColumn",
                        "columnId": "col-done",
                        "cardId": "card-2",
                        "position": "end",
                    },
                ],
            }

    main_module.ai_client = StubClient()
    main_module.board_repo = BoardRepository(tmp_path / "kanban.db")
    main_module.board_repo.initialize()
    main_module.sessions.clear()
    main_module.chat_histories.clear()
    try:
        with TestClient(main_module.app) as client:
            _login(client)
            response = client.post("/api/ai/chat", json={"message": "Move by action style"})
            assert response.status_code == 200
            assert response.json()["appliedOperations"] is True
            done_column = next(
                column
                for column in response.json()["board"]["columns"]
                if column["id"] == "col-done"
            )
            assert "card-2" in done_column["cardIds"]
    finally:
        main_module.ai_client = original_client
        main_module.board_repo = original_repo
        main_module.sessions.clear()
        main_module.chat_histories.clear()


def test_ai_chat_retries_once_for_invalid_structured_response(tmp_path) -> None:
    original_client = main_module.ai_client
    original_repo = main_module.board_repo

    class StubClient:
        def __init__(self) -> None:
            self.calls = 0

        def prompt_structured_chat(
            self, _board: dict, _user_message: str, _conversation: list[dict[str, str]]
        ) -> dict:
            self.calls += 1
            if self.calls == 1:
                return {"final{": -4}
            return {
                "assistantMessage": "Moved on retry.",
                "operations": [{"type": "moveCard", "cardId": "card-2", "toColumnId": "col-done"}],
            }

    stub = StubClient()
    main_module.ai_client = stub
    main_module.board_repo = BoardRepository(tmp_path / "kanban.db")
    main_module.board_repo.initialize()
    main_module.sessions.clear()
    main_module.chat_histories.clear()
    try:
        with TestClient(main_module.app) as client:
            _login(client)
            response = client.post("/api/ai/chat", json={"message": "Move with retry"})
            assert response.status_code == 200
            assert response.json()["appliedOperations"] is True
            assert stub.calls == 2
    finally:
        main_module.ai_client = original_client
        main_module.board_repo = original_repo
        main_module.sessions.clear()
        main_module.chat_histories.clear()
