from aiogram import Bot, F, Router
from aiogram.filters import Command, CommandStart
from aiogram.types import Message

from app.config import Settings
from app.lead_conversation import (
    LeadConversationStore,
    generate_lead_response,
    init_lead_mode,
    is_lead_mode_enabled,
    set_lead_mode,
    build_hot_lead_notification,
)

router = Router()
lead_store: LeadConversationStore | None = None

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
• отвечать потенциальным клиентам в Telegram на обычные сообщения без /

Основные команды:
/agents — показать всех 25 агентов
/day — запустить день продаж
/posts — 10 постов
/dm сообщение клиента — ответ клиенту
/audit описание бизнеса — аудит бизнеса
/proposal описание задачи — КП
/codex описание проекта — ТЗ для Codex

Lead Conversation Agent:
/lead_mode_status — статус автоответов лидам
/lead_mode_on — включить автоответы на обычные сообщения
/lead_mode_off — выключить автоответы на обычные сообщения

Threads:
/threads_day — подготовить 5 постов на сегодня
/threads_post тема поста — подготовить пост
/threads_queue — очередь постов
/threads_publish id_поста — опубликовать пост после подтверждения
/health — статус Railway/Ollama/Threads
/ollama_test — проверить связь с Ollama
/autopost_status — статус автопостинга"""


@router.message(CommandStart())
async def start(message: Message):
    await message.answer(START_TEXT)


@router.message(Command("lead_mode_status"))
async def lead_mode_status(message: Message, settings: Settings):
    init_lead_mode(settings.lead_auto_reply_enabled)
    status = "включён" if is_lead_mode_enabled(settings) else "выключен"
    owner = "задан" if settings.owner_telegram_id else "не задан"
    await message.answer(f"Lead Conversation Agent: {status}\nOWNER_TELEGRAM_ID: {owner}")


@router.message(Command("lead_mode_on"))
async def lead_mode_on(message: Message):
    set_lead_mode(True)
    await message.answer("Lead Conversation Agent включён: обычные сообщения без / будут обрабатываться как лиды.")


@router.message(Command("lead_mode_off"))
async def lead_mode_off(message: Message):
    set_lead_mode(False)
    await message.answer("Lead Conversation Agent выключен: обычные сообщения без / не будут автообрабатываться.")


@router.message(F.text & ~F.text.startswith("/"))
async def lead_conversation(message: Message, settings: Settings, bot: Bot):
    init_lead_mode(settings.lead_auto_reply_enabled)
    if not is_lead_mode_enabled(settings):
        return

    text = (message.text or "").strip()
    if not text:
        return

    user = message.from_user
    user_id = user.id if user else message.chat.id
    username = user.username if user else None
    full_name = user.full_name if user else "Telegram user"

    if lead_store is not None:
        lead_store.save_message(user_id, username, full_name, text)

    response = await generate_lead_response(settings, text)
    await message.answer(response.text)

    if response.is_hot and settings.owner_telegram_id:
        await bot.send_message(
            settings.owner_telegram_id,
            build_hot_lead_notification(user_id, username, full_name, text, response.summary),
        )
