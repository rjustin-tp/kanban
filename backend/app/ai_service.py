from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import httpx

OPENROUTER_MODEL = "openai/gpt-oss-120b"
OPENROUTER_CHAT_COMPLETIONS_URL = "https://openrouter.ai/api/v1/chat/completions"
PROJECT_ENV_PATH = Path(__file__).resolve().parents[2] / ".env"

STRUCTURED_CHAT_SYSTEM_PROMPT = """\
You are an assistant for a kanban board app. Respond with ONLY a JSON object \
matching this shape:

{
  "assistantMessage": string,
  "operations": Operation[]
}

Each Operation has a "type" field that determines its other fields. Use exactly \
these snake_case type strings:

1. {"type": "create_card", "columnId": string, "title": string, "details"?: string, "cardId"?: string, "index"?: int}
2. {"type": "update_card", "cardId": string, "title"?: string, "details"?: string}  (must include title and/or details)
3. {"type": "delete_card", "cardId": string}
4. {"type": "move_card", "cardId": string, "toColumnId": string, "toIndex"?: int}
5. {"type": "create_column", "title": string, "columnId"?: string, "index"?: int}
6. {"type": "update_column", "columnId": string, "title": string}
7. {"type": "delete_column", "columnId": string}  (also deletes cards inside it)
8. {"type": "move_column", "columnId": string, "toIndex": int}

All cardId / columnId values must reference ids that exist in the provided board \
state. Use [] for operations when no mutations are needed. Do not include any \
keys other than the ones listed above."""


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

        return _extract_assistant_content(response.json()).strip()

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
                {"role": "system", "content": STRUCTURED_CHAT_SYSTEM_PROMPT},
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

        content = _extract_assistant_content(response.json())

        try:
            parsed = json.loads(content)
        except json.JSONDecodeError as error:
            raise OpenRouterRequestError("OpenRouter response was not valid JSON.") from error

        if not isinstance(parsed, dict):
            raise OpenRouterRequestError("OpenRouter response JSON must be an object.")
        return parsed


def _extract_assistant_content(response_data: dict[str, Any]) -> str:
    choices = response_data.get("choices")
    if not isinstance(choices, list) or not choices:
        raise OpenRouterRequestError("OpenRouter response had no choices.")
    message = choices[0].get("message") if isinstance(choices[0], dict) else None
    content = message.get("content") if isinstance(message, dict) else None
    if not isinstance(content, str) or not content.strip():
        raise OpenRouterRequestError("OpenRouter response did not include assistant text.")
    return content


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
