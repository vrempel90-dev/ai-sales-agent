import asyncio
import logging
from aiogram import Bot, Dispatcher
from app.config import get_settings
from app.handlers import agents, sales
from app.post_queue import PostQueue
from app.threads_scheduler import run_threads_scheduler

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)


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
    dp = Dispatcher()
    dp["settings"] = settings
    dp.include_router(sales.router)
    dp.include_router(agents.router)

    if settings.threads_auto_posting_enabled:
        asyncio.create_task(run_threads_scheduler(settings, queue))
    else:
        logger.info("Auto Threads Posting: disabled")

    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
