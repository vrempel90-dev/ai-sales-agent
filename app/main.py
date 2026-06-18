import asyncio
import logging
from aiogram import Bot, Dispatcher
from aiogram.types import BotCommand
from datetime import datetime
from zoneinfo import ZoneInfo
from app.config import get_settings
from app.handlers import agents, comments, sales
from app.growth_state import growth_runtime
from app.lead_store import LeadConversationService
from app.post_queue import PostQueue
from app.threads_scheduler import run_threads_scheduler

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)

BOT_COMMANDS = [
    BotCommand(command="start", description="AI Growth Manager"),
    BotCommand(command="autopilot_status", description="Статус Safe Autopilot"),
    BotCommand(command="growth_status", description="Статус Growth Manager"),
    BotCommand(command="growth_report", description="Отчёт по росту"),
    BotCommand(command="threads_queue", description="Очередь Threads"),
    BotCommand(command="threads_next", description="Следующий draft"),
    BotCommand(command="comment_discovery_status", description="Статус комментариев"),
    BotCommand(command="comment_queue", description="Очередь комментариев"),
    BotCommand(command="health", description="Статус системы"),
    BotCommand(command="sales_status", description="Статус Sales Closing Agent"),
    BotCommand(command="sales_preview", description="Предпросмотр ответа лиду"),
    BotCommand(command="whatsapp_status", description="Настройки WhatsApp"),
    BotCommand(command="positioning", description="Позиционирование"),
]


async def run_daily_growth_report(bot: Bot, settings) -> None:
    while True:
        try:
            now = datetime.now(ZoneInfo(settings.growth_report_timezone))
            today = now.date().isoformat()
            if (
                settings.growth_daily_report_enabled
                and settings.owner_telegram_id is not None
                and now.hour == settings.growth_report_hour
                and growth_runtime.last_report_date != today
            ):
                await bot.send_message(settings.owner_telegram_id, agents.build_growth_report(settings))
                growth_runtime.last_report_date = today
                growth_runtime.last_action = "daily growth report отправлен владельцу"
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            growth_runtime.last_error = f"daily report: {exc}"
            logger.exception("Daily growth report failed")
        await asyncio.sleep(60)


async def main():
    settings = get_settings()
    queue = PostQueue(settings.database_path)
    agents.post_queue = queue

    logger.info("bot started")
    logger.info("Ollama base URL: %s", settings.ollama_base_url)
    logger.info("Ollama model: %s", settings.ollama_model)
    logger.info("database path: %s", settings.database_path)
    logger.info("Threads API configured: %s", "yes" if settings.threads_api_configured else "no")
    logger.info("auto posting enabled: %s", "yes" if settings.threads_auto_posting_enabled else "no")

    bot = Bot(settings.telegram_bot_token)
    await bot.set_my_commands(BOT_COMMANDS)
    dp = Dispatcher()
    dp["settings"] = settings
    dp["lead_service"] = LeadConversationService(
        settings.database_path,
        settings.lead_auto_reply_enabled,
    )
    dp.include_router(sales.router)
    dp.include_router(agents.router)
    dp.include_router(comments.router)

    if settings.threads_auto_posting_enabled:
        asyncio.create_task(run_threads_scheduler(settings, queue))
    else:
        logger.info("Auto Threads Posting: disabled")
    if settings.growth_daily_report_enabled and settings.owner_telegram_id is not None:
        asyncio.create_task(run_daily_growth_report(bot, settings))

    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
