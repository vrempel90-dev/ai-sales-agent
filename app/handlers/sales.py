from aiogram import Router
from aiogram.filters import CommandStart
from aiogram.types import Message

router = Router()

START_TEXT = """Привет. Я AI Sales Agent для продажи AI-чат-ботов бизнесу.

Я умею:
• писать посты
• делать Threads-ветки
• отвечать на комментарии
• помогать с личкой
• обрабатывать возражения
• делать аудит бизнеса
• создавать офферы и КП
• писать ТЗ для Codex
• проектировать ботов
• делать тесты
• готовить посты для Threads и публиковать их после подтверждения

Основные команды:
/agents — показать всех 25 агентов
/day — запустить день продаж
/posts — 10 постов
/dm <сообщение клиента> — ответ клиенту
/audit <описание бизнеса> — аудит бизнеса
/proposal <задача клиента> — КП
/codex <описание проекта> — ТЗ для Codex

Threads:
/threads_day — подготовить 5 постов на сегодня
/threads_post <тема> — подготовить пост
/threads_queue — очередь постов
/threads_publish <id> — опубликовать пост после подтверждения
/health — статус Railway/Ollama/Threads
/autopost_status — статус автопостинга"""

@router.message(CommandStart())
async def start(message: Message):
    await message.answer(START_TEXT)
