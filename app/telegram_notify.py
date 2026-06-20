"""Telegram notifications for hot leads."""
import logging
import httpx
from app.config import get_settings
from app.models import Lead

logger = logging.getLogger(__name__)


def build_hot_lead_message(lead: Lead) -> str:
    return f"""🔥 ГОРЯЧИЙ ЛИД

Ник: @{lead.username or 'unknown'}
Ниша: {lead.business_type or '-'}
Канал заявок: {lead.channel or '-'}
Боль: {lead.pain or '-'}
Что хочет: {lead.desired_solution or '-'}
Оценка лида: {lead.lead_score}
Кратко: {lead.summary or '-'}
Следующий шаг: {lead.recommended_next_step or '-'}
Ссылка на диалог: {lead.source_url or '-'}"""


async def send_hot_lead(lead: Lead) -> bool:
    settings = get_settings()
    if not settings.telegram_configured:
        logger.warning("Telegram is not configured; hot lead notification skipped")
        return False
    url = f"https://api.telegram.org/bot{settings.telegram_bot_token}/sendMessage"
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            response = await client.post(url, json={"chat_id": settings.telegram_chat_id, "text": build_hot_lead_message(lead)})
            response.raise_for_status()
            return True
    except Exception:
        logger.exception("Telegram hot lead notification failed")
        return False
