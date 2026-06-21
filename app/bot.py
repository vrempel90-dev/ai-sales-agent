"""Telegram bot bootstrap and polling lifecycle."""
import logging

from aiogram import Bot, Dispatcher

from app.config import get_settings
from app.handlers import agents, autonomous_threads, comments, sales
from app.lead_store import LeadConversationService

logger = logging.getLogger(__name__)


def create_dispatcher() -> Dispatcher:
    """Create a dispatcher with all existing Telegram command handlers wired in."""
    settings = get_settings()
    dispatcher = Dispatcher(
        settings=settings,
        lead_service=LeadConversationService(settings.database_path, enabled=settings.lead_auto_reply_enabled),
    )
    dispatcher.include_router(sales.router)
    dispatcher.include_router(agents.router)
    dispatcher.include_router(autonomous_threads.router)
    dispatcher.include_router(comments.router)
    return dispatcher


async def start_telegram_bot() -> None:
    """Start Telegram long polling; intended to run as a background task."""
    settings = get_settings()
    if not settings.telegram_bot_token:
        logger.info("Telegram bot token missing; polling not started")
        return

    bot = Bot(token=settings.telegram_bot_token)
    dispatcher = create_dispatcher()
    logger.info("Telegram bot polling started")
    try:
        if hasattr(bot, "delete_webhook"):
            await bot.delete_webhook(drop_pending_updates=True)
        await dispatcher.start_polling(bot)
    except Exception:
        logger.exception("Telegram polling stopped with an error")
        raise
    finally:
        if hasattr(bot, "close"):
            await bot.close()
