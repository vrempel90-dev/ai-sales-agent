import logging
from typing import Any

import httpx

from .config import Settings

OLLAMA_ERROR = "Ollama не отвечает. Проверьте, что модель запущена."
OLLAMA_TIMEOUT_SECONDS = 180
_RESPONSE_BODY_LOG_LIMIT = 2000

logger = logging.getLogger(__name__)


class OllamaResponseError(Exception):
    def __init__(self, message: str, response: httpx.Response):
        super().__init__(message)
        self.response = response


def _truncate_response_body(response: httpx.Response | None) -> str | None:
    if response is None:
        return None

    body = response.text
    if len(body) > _RESPONSE_BODY_LOG_LIMIT:
        return f"{body[:_RESPONSE_BODY_LOG_LIMIT]}...<truncated>"
    return body


def _log_ollama_error(endpoint: str, exc: Exception) -> None:
    response = getattr(exc, "response", None)
    status_code = getattr(response, "status_code", None)
    response_body = _truncate_response_body(response) if isinstance(response, httpx.Response) else None

    logger.warning(
        "Ollama request failed: endpoint=%s status_code=%s exception_type=%s response_body=%r",
        endpoint,
        status_code,
        type(exc).__name__,
        response_body,
    )


async def _post_ollama(client: httpx.AsyncClient, settings: Settings, endpoint: str, payload: dict[str, Any]) -> dict[str, Any]:
    url = f"{settings.ollama_base_url.rstrip('/')}{endpoint}"
    response = await client.post(url, json=payload)
    response.raise_for_status()
    try:
        return response.json()
    except ValueError as exc:
        raise OllamaResponseError("Ollama returned invalid JSON", response) from exc


def _parse_chat_response(data: dict[str, Any]) -> str:
    content = data["message"]["content"]
    return content.strip() or "Не получилось получить ответ от модели."


def _parse_generate_response(data: dict[str, Any]) -> str:
    content = data["response"]
    return content.strip() or "Не получилось получить ответ от модели."


async def ask_ollama(settings: Settings, prompt: str) -> str:
    chat_payload = {
        "model": settings.ollama_model,
        "messages": [{"role": "user", "content": prompt}],
        "stream": False,
    }
    generate_payload = {
        "model": settings.ollama_model,
        "prompt": prompt,
        "stream": False,
    }

    async with httpx.AsyncClient(timeout=OLLAMA_TIMEOUT_SECONDS) as client:
        try:
            data = await _post_ollama(client, settings, "/api/chat", chat_payload)
            return _parse_chat_response(data)
        except (httpx.HTTPError, OllamaResponseError, KeyError, TypeError, AttributeError) as exc:
            _log_ollama_error("/api/chat", exc)

        try:
            data = await _post_ollama(client, settings, "/api/generate", generate_payload)
            return _parse_generate_response(data)
        except (httpx.HTTPError, OllamaResponseError, KeyError, TypeError, AttributeError) as exc:
            _log_ollama_error("/api/generate", exc)
            raise RuntimeError(OLLAMA_ERROR) from exc
