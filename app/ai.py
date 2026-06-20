"""OpenAI wrapper with safe fallbacks and basic retries."""
import json
import logging
import time
from typing import Any
from openai import OpenAI
from app.config import get_settings

logger = logging.getLogger(__name__)


def _fallback_text(user_prompt: str) -> str:
    return "Понял. А какой у вас бизнес? Тогда смогу точнее сказать, какой AI-агент подойдет первым."


def generate_text(system_prompt: str, user_prompt: str) -> str:
    settings = get_settings()
    if not settings.openai_api_key:
        logger.warning("OPENAI_API_KEY is missing; returning fallback text")
        return _fallback_text(user_prompt)
    client = OpenAI(api_key=settings.openai_api_key)
    for attempt in range(3):
        try:
            response = client.chat.completions.create(
                model=settings.openai_model,
                messages=[{"role": "system", "content": system_prompt}, {"role": "user", "content": user_prompt}],
                temperature=0.7,
            )
            return response.choices[0].message.content or ""
        except Exception:
            logger.exception("OpenAI text generation failed on attempt %s", attempt + 1)
            time.sleep(0.5 * (attempt + 1))
    return _fallback_text(user_prompt)


def generate_json(system_prompt: str, user_prompt: str) -> dict[str, Any]:
    settings = get_settings()
    if not settings.openai_api_key:
        logger.warning("OPENAI_API_KEY is missing; returning fallback JSON")
        return {"business_type": "", "pain": "", "desired_solution": "", "channel": "", "lead_score": 0, "lead_status": "cold", "should_notify_viktor": False, "summary": user_prompt[:200], "recommended_next_step": "Продолжить квалификацию"}
    text = generate_text(system_prompt, user_prompt)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        logger.exception("OpenAI returned non-JSON response")
        return {"business_type": "", "pain": "", "desired_solution": "", "channel": "", "lead_score": 0, "lead_status": "cold", "should_notify_viktor": False, "summary": text[:200], "recommended_next_step": "Уточнить бизнес, канал заявок и задачу"}
