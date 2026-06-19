import asyncio
import logging
from aiogram import Bot, Dispatcher
from aiogram.types import BotCommand
from datetime import datetime
from zoneinfo import ZoneInfo
from app.config import get_settings
from app.handlers import agents, comments, sales, autonomous_threads
from app.growth_state import growth_runtime
from app.lead_store import LeadConversationService
from app.post_queue import PostQueue
from app.threads_scheduler import run_threads_scheduler

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)

BOT_COMMANDS = [
    BotCommand(command="start", description="главное меню"),
    BotCommand(command="today", description="отчёт за сегодня"),
    BotCommand(command="plan", description="план на день"),
    BotCommand(command="content", description="контент"),
    BotCommand(command="leads", description="клиенты"),
    BotCommand(command="sales", description="продажи"),
    BotCommand(command="status", description="автопилот"),
    BotCommand(command="system", description="система"),
    BotCommand(command="next_post", description="следующий пост"),
    BotCommand(command="next_lead", description="следующий лид"),
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
    dp.include_router(autonomous_threads.router)
    dp.include_router(comments.router)

    if settings.threads_auto_posting_enabled:
        asyncio.create_task(run_threads_scheduler(settings, queue))
    else:
        logger.info("Auto Threads Posting: disabled")
    if settings.growth_daily_report_enabled and settings.owner_telegram_id is not None:
        asyncio.create_task(run_daily_growth_report(bot, settings))
    if settings.autonomous_threads_agent_enabled and settings.autonomous_threads_agent_auto_start:
        agent = autonomous_threads.get_agent(settings)
        agent.runtime_enabled = True
        logger.info("Autonomous Threads Growth Agent auto-started")
        if settings.owner_telegram_id is not None and settings.autonomous_threads_owner_notify:
            await bot.send_message(settings.owner_telegram_id, agent.startup_summary())

    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
