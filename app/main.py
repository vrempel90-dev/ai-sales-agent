import asyncio
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from app.config import get_settings, Settings
from app.handlers import agents, sales

async def main():
    settings = get_settings()
    bot = Bot(settings.telegram_bot_token, default=DefaultBotProperties(parse_mode="HTML"))
    dp = Dispatcher()
    dp["settings"] = settings
    dp.include_router(sales.router)
    dp.include_router(agents.router)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
