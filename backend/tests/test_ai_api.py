from fastapi.testclient import TestClient

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
