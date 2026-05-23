from __future__ import annotations

import os

import httpx

OPENROUTER_MODEL = "openai/gpt-oss-120b"
OPENROUTER_CHAT_COMPLETIONS_URL = "https://openrouter.ai/api/v1/chat/completions"


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
        api_key = os.getenv("OPENROUTER_API_KEY")
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
