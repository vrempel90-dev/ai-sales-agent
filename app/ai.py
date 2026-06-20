"""LLM provider wrapper with safe fallbacks, JSON parsing, and basic retries."""
import json
import logging
import time
from typing import Any

import httpx
from app.config import get_settings

logger = logging.getLogger(__name__)

_SAFE_JSON_FALLBACK: dict[str, Any] = {
    "business_type": "",
    "pain": "",
    "desired_solution": "",
    "channel": "",
    "lead_score": 0,
    "lead_status": "cold",
    "should_notify_viktor": False,
    "summary": "",
    "recommended_next_step": "",
}


def _fallback_text(user_prompt: str) -> str:
    return "Понял. А какой у вас бизнес? Тогда смогу точнее сказать, какой AI-агент подойдет первым."


def _fallback_json() -> dict[str, Any]:
    return dict(_SAFE_JSON_FALLBACK)


def _generate_openai_text(system_prompt: str, user_prompt: str) -> str:
    settings = get_settings()
    if not settings.openai_api_key:
        logger.warning("OPENAI_API_KEY is missing; returning fallback text")
        return _fallback_text(user_prompt)

    from openai import OpenAI

    client = OpenAI(api_key=settings.openai_api_key)
    for attempt in range(3):
        try:
            response = client.chat.completions.create(
                model=settings.openai_model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.7,
            )
            return response.choices[0].message.content or ""
        except Exception:
            logger.exception("OpenAI text generation failed on attempt %s", attempt + 1)
            time.sleep(0.5 * (attempt + 1))

    logger.warning("OpenAI provider unavailable after retries; returning fallback text")
    return _fallback_text(user_prompt)


def _generate_ollama_text(system_prompt: str, user_prompt: str) -> str:
    settings = get_settings()
    if not settings.ollama_base_url or not settings.ollama_model:
        logger.warning("Ollama configuration is incomplete; returning fallback text")
        return _fallback_text(user_prompt)

    url = f"{settings.ollama_base_url.rstrip('/')}/api/chat"
    payload = {
        "model": settings.ollama_model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "stream": False,
    }

    for attempt in range(3):
        try:
            response = httpx.post(url, json=payload, timeout=settings.ollama_timeout_seconds)
            response.raise_for_status()
            data = response.json()
            content = data["message"]["content"]
            return str(content or "")
        except (httpx.HTTPError, ValueError, KeyError, TypeError):
            logger.exception("Ollama text generation failed on attempt %s", attempt + 1)
            time.sleep(0.5 * (attempt + 1))

    logger.warning("Ollama provider unavailable after retries; returning fallback text")
    return _fallback_text(user_prompt)


def generate_text(system_prompt: str, user_prompt: str) -> str:
    """Generate text with the selected LLM provider or return a safe fallback."""
    settings = get_settings()
    provider = settings.llm_provider.strip().lower()

    if provider == "ollama":
        return _generate_ollama_text(system_prompt, user_prompt)
    if provider == "openai":
        return _generate_openai_text(system_prompt, user_prompt)

    logger.warning("Unknown LLM_PROVIDER=%r; returning fallback text", settings.llm_provider)
    return _fallback_text(user_prompt)


def _parse_json_from_text(text: str) -> dict[str, Any]:
    try:
        parsed = json.loads(text)
        if isinstance(parsed, dict):
            return parsed
    except json.JSONDecodeError:
        pass

    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and start < end:
        try:
            parsed = json.loads(text[start : end + 1])
            if isinstance(parsed, dict):
                return parsed
        except json.JSONDecodeError:
            pass

    logger.warning("LLM returned non-JSON response; returning fallback JSON")
    return _fallback_json()


def generate_json(system_prompt: str, user_prompt: str) -> dict[str, Any]:
    """Generate and parse JSON with the selected LLM provider or return a safe fallback."""
    text = generate_text(system_prompt, user_prompt)
    if not text:
        logger.warning("LLM returned an empty response; returning fallback JSON")
        return _fallback_json()
    return _parse_json_from_text(text)
