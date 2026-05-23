from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import httpx

OPENROUTER_MODEL = "openai/gpt-oss-120b"
OPENROUTER_CHAT_COMPLETIONS_URL = "https://openrouter.ai/api/v1/chat/completions"
PROJECT_ENV_PATH = Path(__file__).resolve().parents[2] / ".env"


class OpenRouterConfigError(RuntimeError):
    pass


class OpenRouterRequestError(RuntimeError):
    pass


class OpenRouterTimeoutError(RuntimeError):
    pass


class OpenRouterClient:
    def __init__(self, timeout_seconds: float = 20.0, transport: httpx.BaseTransport | None = None):
        self.timeout_seconds = timeout_seconds
        self.transport = transport

    def prompt_text(self, prompt: str) -> str:
        api_key = _resolve_openrouter_api_key()
        if not api_key:
            raise OpenRouterConfigError("Missing OPENROUTER_API_KEY.")

        payload = {
            "model": OPENROUTER_MODEL,
            "messages": [{"role": "user", "content": prompt}],
        }
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

        try:
            with httpx.Client(timeout=self.timeout_seconds, transport=self.transport) as client:
                response = client.post(
                    OPENROUTER_CHAT_COMPLETIONS_URL,
                    headers=headers,
                    json=payload,
                )
        except httpx.TimeoutException as error:
            raise OpenRouterTimeoutError("OpenRouter request timed out.") from error
        except httpx.HTTPError as error:
            raise OpenRouterRequestError(f"OpenRouter request failed: {error}") from error

        if response.status_code != 200:
            raise OpenRouterRequestError(
                f"OpenRouter request failed with status {response.status_code}."
            )

        response_data = response.json()
        content = (
            response_data.get("choices", [{}])[0]
            .get("message", {})
            .get("content")
        )
        if not isinstance(content, str) or not content.strip():
            raise OpenRouterRequestError("OpenRouter response did not include assistant text.")

        return content.strip()

    def prompt_structured_chat(
        self,
        board: dict[str, Any],
        user_message: str,
        conversation: list[dict[str, str]],
    ) -> dict[str, Any]:
        api_key = _resolve_openrouter_api_key()
        if not api_key:
            raise OpenRouterConfigError("Missing OPENROUTER_API_KEY.")

        payload = {
            "model": OPENROUTER_MODEL,
            "response_format": {"type": "json_object"},
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "You are an assistant for a kanban app. Respond only with JSON object "
                        "matching this shape: {assistantMessage: string, operations?: array}."
                    ),
                },
                {
                    "role": "user",
                    "content": json.dumps(
                        {
                            "board": board,
                            "userMessage": user_message,
                            "conversation": conversation,
                        }
                    ),
                },
            ],
        }
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

        try:
            with httpx.Client(timeout=self.timeout_seconds, transport=self.transport) as client:
                response = client.post(
                    OPENROUTER_CHAT_COMPLETIONS_URL,
                    headers=headers,
                    json=payload,
                )
        except httpx.TimeoutException as error:
            raise OpenRouterTimeoutError("OpenRouter request timed out.") from error
        except httpx.HTTPError as error:
            raise OpenRouterRequestError(f"OpenRouter request failed: {error}") from error

        if response.status_code != 200:
            raise OpenRouterRequestError(
                f"OpenRouter request failed with status {response.status_code}."
            )

        response_data = response.json()
        content = (
            response_data.get("choices", [{}])[0]
            .get("message", {})
            .get("content")
        )
        if not isinstance(content, str) or not content.strip():
            raise OpenRouterRequestError("OpenRouter response did not include assistant text.")

        try:
            parsed = json.loads(content)
        except json.JSONDecodeError as error:
            raise OpenRouterRequestError("OpenRouter response was not valid JSON.") from error

        if not isinstance(parsed, dict):
            raise OpenRouterRequestError("OpenRouter response JSON must be an object.")
        return parsed


def _resolve_openrouter_api_key() -> str | None:
    api_key = os.getenv("OPENROUTER_API_KEY")
    if api_key:
        return api_key

    if not PROJECT_ENV_PATH.exists():
        return None

    try:
        for line in PROJECT_ENV_PATH.read_text().splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith("#") or "=" not in stripped:
                continue
            key, value = stripped.split("=", 1)
            if key.strip() != "OPENROUTER_API_KEY":
                continue
            cleaned = value.strip().strip("'\"")
            return cleaned or None
    except OSError:
        return None

    return None
