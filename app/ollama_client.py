import logging
from typing import Any

import httpx

from .config import Settings

OLLAMA_ERROR = "Ollama не отвечает. Проверьте, что модель запущена."
OLLAMA_CRASH_ERROR = (
    "Ollama на сервере упала при генерации. Это проблема Ollama/Railway, а не Telegram-бота. "
    "Попробуйте уменьшить модель или параметры OLLAMA_NUM_CTX=512, OLLAMA_NUM_THREAD=1."
)
OLLAMA_TIMEOUT_SECONDS = 180
_RESPONSE_BODY_LOG_LIMIT = 2000

logger = logging.getLogger(__name__)


class OllamaResponseError(Exception):
    def __init__(self, message: str, response: httpx.Response):
        super().__init__(message)
        self.response = response


def build_ollama_options(settings: Settings) -> dict[str, int | float]:
    return {
        "num_ctx": settings.ollama_num_ctx,
        "num_predict": settings.ollama_num_predict,
        "num_thread": settings.ollama_num_thread,
        "temperature": settings.ollama_temperature,
        "top_p": settings.ollama_top_p,
    }


def _truncate_response_body(response: httpx.Response | None) -> str | None:
    if response is None:
        return None

    body = response.text
    if len(body) > _RESPONSE_BODY_LOG_LIMIT:
        return f"{body[:_RESPONSE_BODY_LOG_LIMIT]}...<truncated>"
    return body


def _is_ollama_crash(exc: Exception) -> bool:
    response = getattr(exc, "response", None)
    if not isinstance(response, httpx.Response) or response.status_code != 500:
        return False

    body = response.text.lower()
    return "segmentation fault" in body or "llama-server process has terminated" in body


def _user_facing_ollama_error(exc: Exception) -> str:
    if _is_ollama_crash(exc):
        return OLLAMA_CRASH_ERROR
    return OLLAMA_ERROR


def _short_error_text(exc: Exception) -> str:
    if _is_ollama_crash(exc):
        return OLLAMA_CRASH_ERROR

    response = getattr(exc, "response", None)
    if isinstance(response, httpx.Response):
        body = response.text.strip().replace("\n", " ")
        if len(body) > 300:
            body = f"{body[:300]}..."
        return f"HTTP {response.status_code}: {body or response.reason_phrase}"

    text = str(exc).strip().replace("\n", " ")
    if len(text) > 300:
        text = f"{text[:300]}..."
    return text or type(exc).__name__


def _log_ollama_error(endpoint: str, exc: Exception, url: str | None = None) -> None:
    response = getattr(exc, "response", None)
    status_code = getattr(response, "status_code", None)
    response_body = _truncate_response_body(response) if isinstance(response, httpx.Response) else None

    logger.warning(
        "Ollama request failed: endpoint=%s url=%s status_code=%s exception_type=%s response_body=%r",
        endpoint,
        url,
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


def _chat_payload(settings: Settings, prompt: str) -> dict[str, Any]:
    return {
        "model": settings.ollama_model,
        "messages": [{"role": "user", "content": prompt}],
        "stream": False,
        "options": build_ollama_options(settings),
    }


def _generate_payload(settings: Settings, prompt: str) -> dict[str, Any]:
    return {
        "model": settings.ollama_model,
        "prompt": prompt,
        "stream": False,
        "options": build_ollama_options(settings),
    }


async def ask_ollama(settings: Settings, prompt: str) -> str:
    async with httpx.AsyncClient(timeout=OLLAMA_TIMEOUT_SECONDS) as client:
        try:
            data = await _post_ollama(client, settings, "/api/chat", _chat_payload(settings, prompt))
            return _parse_chat_response(data)
        except (httpx.HTTPError, OllamaResponseError, KeyError, TypeError, AttributeError) as exc:
            _log_ollama_error("/api/chat", exc, f"{settings.ollama_base_url.rstrip('/')}/api/chat")
            if _is_ollama_crash(exc):
                raise RuntimeError(OLLAMA_CRASH_ERROR) from exc

        try:
            data = await _post_ollama(client, settings, "/api/generate", _generate_payload(settings, prompt))
            return _parse_generate_response(data)
        except (httpx.HTTPError, OllamaResponseError, KeyError, TypeError, AttributeError) as exc:
            _log_ollama_error("/api/generate", exc, f"{settings.ollama_base_url.rstrip('/')}/api/generate")
            raise RuntimeError(_user_facing_ollama_error(exc)) from exc


async def test_ollama(settings: Settings) -> tuple[bool, str]:
    try:
        response = await ask_ollama(settings, "Ответь одним словом: работает")
    except RuntimeError as exc:
        return False, str(exc)
    except Exception as exc:
        _log_ollama_error("/api/chat", exc, f"{settings.ollama_base_url.rstrip('/')}/api/chat")
        return False, _short_error_text(exc)

    return True, response
