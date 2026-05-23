import httpx
import pytest

from app import ai_service
from app.ai_service import (
    OPENROUTER_MODEL,
    OpenRouterClient,
    OpenRouterConfigError,
    OpenRouterRequestError,
    OpenRouterTimeoutError,
)


def test_prompt_text_returns_assistant_content(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url == httpx.URL("https://openrouter.ai/api/v1/chat/completions")
        payload = request.read().decode("utf-8")
        assert OPENROUTER_MODEL in payload
        assert "2+2" in payload
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": "4"}}]},
        )

    transport = httpx.MockTransport(handler)
    client = OpenRouterClient(transport=transport)

    assert client.prompt_text("2+2") == "4"


def test_prompt_text_raises_when_api_key_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    monkeypatch.setattr(ai_service, "PROJECT_ENV_PATH", ai_service.PROJECT_ENV_PATH.parent / ".missing-env")
    client = OpenRouterClient()

    with pytest.raises(OpenRouterConfigError, match="OPENROUTER_API_KEY"):
        client.prompt_text("2+2")


def test_prompt_text_raises_for_non_200_response(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")

    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(503, json={"error": "unavailable"})

    client = OpenRouterClient(transport=httpx.MockTransport(handler))

    with pytest.raises(OpenRouterRequestError, match="status 503"):
        client.prompt_text("2+2")


def test_prompt_text_raises_for_timeout(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")

    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("timed out", request=request)

    client = OpenRouterClient(transport=httpx.MockTransport(handler))

    with pytest.raises(OpenRouterTimeoutError, match="timed out"):
        client.prompt_text("2+2")


def test_prompt_structured_chat_returns_json_object(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")

    def handler(request: httpx.Request) -> httpx.Response:
        payload = request.read().decode("utf-8")
        assert OPENROUTER_MODEL in payload
        assert "response_format" in payload
        assert "Move this card" in payload
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "message": {
                            "content": '{"assistantMessage":"Done","operations":[]}'
                        }
                    }
                ]
            },
        )

    client = OpenRouterClient(transport=httpx.MockTransport(handler))
    result = client.prompt_structured_chat(
        board={"columns": [], "cards": {}},
        user_message="Move this card",
        conversation=[{"role": "user", "content": "Move this card"}],
    )
    assert result == {"assistantMessage": "Done", "operations": []}


def test_prompt_structured_chat_raises_for_non_json_content(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")

    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": "not-json"}}]},
        )

    client = OpenRouterClient(transport=httpx.MockTransport(handler))
    with pytest.raises(OpenRouterRequestError, match="not valid JSON"):
        client.prompt_structured_chat(
            board={"columns": [], "cards": {}},
            user_message="Hello",
            conversation=[],
        )


def test_prompt_text_reads_api_key_from_project_env_file(
    monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    env_path = tmp_path / ".env"
    env_path.write_text("OPENROUTER_API_KEY=env-file-key\n")
    monkeypatch.setattr(ai_service, "PROJECT_ENV_PATH", env_path)

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["Authorization"] == "Bearer env-file-key"
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": "4"}}]},
        )

    client = OpenRouterClient(transport=httpx.MockTransport(handler))
    assert client.prompt_text("2+2") == "4"
