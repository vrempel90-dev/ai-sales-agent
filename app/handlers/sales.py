from aiogram import F, Router
from aiogram.filters import Command, CommandStart
from aiogram.types import Message
from app.config import Settings
from app.lead_agent import HOT_LEAD_THRESHOLD, PRICE_RANGES, build_lead_reply, hot_lead_notification
from app.lead_store import LeadConversationService

router = Router()

START_TEXT = """Привет. Я AI Growth Manager для Threads: Senior SMM Growth Director + Safe Autopilot + growth strategist + sales-помощник.

Главное:
• /autopilot_status — всё ли работает
• /growth_report — отчёт за день
• /growth_plan — план на сегодня

Посты:
• /threads_next — следующий пост
• /threads_queue — очередь
• /growth_refill — пополнить очередь
• /growth_rebuild — пересобрать очередь

Продажи:
• /sales_preview текст — проверить ответ клиенту
• /sales_status — статус продаж
• /whatsapp_status — WhatsApp

Система:
• /health
• /ollama_test

Расширенные команды доступны, но в основном меню скрыты."""

@router.message(CommandStart())
async def start(message: Message):
    await message.answer(START_TEXT)


def owner_access_error(message: Message, settings: Settings) -> str | None:
    if settings.owner_telegram_id is None:
        return "OWNER_TELEGRAM_ID не настроен."
    if message.from_user.id != settings.owner_telegram_id:
        return "Эта команда доступна только владельцу."
    return None


async def require_owner(message: Message, settings: Settings) -> bool:
    error = owner_access_error(message, settings)
    if error:
        await message.answer(error)
        return False
    return True


@router.message(Command("lead_mode_on"))
async def lead_mode_on(
    message: Message,
    settings: Settings,
    lead_service: LeadConversationService,
):
    if not await require_owner(message, settings):
        return
    lead_service.enabled = True
    await message.answer("Lead auto-reply включён.")


@router.message(Command("lead_mode_off"))
async def lead_mode_off(
    message: Message,
    settings: Settings,
    lead_service: LeadConversationService,
):
    if not await require_owner(message, settings):
        return
    lead_service.enabled = False
    await message.answer("Lead auto-reply выключен.")


@router.message(Command("lead_mode_status"))
async def lead_mode_status(
    message: Message,
    settings: Settings,
    lead_service: LeadConversationService,
):
    if not await require_owner(message, settings):
        return
    await message.answer(
        f"Lead auto-reply: {'включён' if lead_service.enabled else 'выключен'}"
    )


@router.message(Command("dm_preview"))
async def dm_preview(message: Message, settings: Settings):
    if not await require_owner(message, settings):
        return
    text = (message.text or "").split(maxsplit=1)
    if len(text) < 2 or not text[1].strip():
        await message.answer("Добавьте сообщение. Пример:\n/dm_preview Сколько стоит бот?")
        return
    reply = build_lead_reply(
        text[1].strip(),
        settings.whatsapp_contact_link,
        settings.whatsapp_phone,
    )
    await message.answer(f"Предпросмотр ({reply.stage}):\n\n{reply.text}")


@router.message(Command("sales_preview"))
async def sales_preview(message: Message, settings: Settings):
    if not await require_owner(message, settings):
        return
    parts = (message.text or "").split(maxsplit=1)
    if len(parts) < 2 or not parts[1].strip():
        await message.answer("Добавьте текст лида. Пример:\n/sales_preview Хочу AI-бота для салона")
        return
    reply = build_lead_reply(parts[1].strip(), settings.whatsapp_contact_link, settings.whatsapp_phone)
    notification = hot_lead_notification(message, reply) if reply.is_hot else "не отправляется: лид ещё не hot"
    await message.answer(
        f"Ответ агента:\n{reply.text}\n\n"
        f"Lead score: {reply.lead_score} ({reply.score})\n"
        f"Recommended next step: {reply.next_step}\n\n"
        f"Owner notification preview:\n{notification}"
    )


@router.message(Command("sales_status"))
async def sales_status(
    message: Message,
    settings: Settings,
    lead_service: LeadConversationService,
):
    if not await require_owner(message, settings):
        return
    await message.answer(
        "AI Sales Closing Agent enabled: yes\n"
        f"Lead auto reply enabled: {'yes' if lead_service.enabled else 'no'}\n"
        f"WhatsApp configured: {'yes' if settings.whatsapp_contact_link or settings.whatsapp_phone else 'no'}\n"
        f"Owner notifications configured: {'yes' if settings.owner_telegram_id is not None else 'no'}\n"
        f"Price ranges loaded: {len(PRICE_RANGES)}\n"
        f"Hot lead threshold: {HOT_LEAD_THRESHOLD}\n"
        f"Last lead summary:\n{lead_service.store.last_summary()}"
    )


@router.message(Command("whatsapp_status"))
async def whatsapp_status(message: Message, settings: Settings):
    if not await require_owner(message, settings):
        return
    await message.answer(
        f"WHATSAPP_CONTACT_LINK настроен: {'yes' if settings.whatsapp_contact_link else 'no'}\n"
        f"WHATSAPP_PHONE настроен: {'yes' if settings.whatsapp_phone else 'no'}\n"
        f"OWNER_TELEGRAM_ID настроен: {'yes' if settings.owner_telegram_id is not None else 'no'}\n"
        f"LEAD_AUTO_REPLY_ENABLED: {'true' if settings.lead_auto_reply_enabled else 'false'}"
    )


@router.message(F.text & ~F.text.startswith("/"))
async def lead_message(
    message: Message,
    settings: Settings,
    lead_service: LeadConversationService,
):
    if not lead_service.enabled:
        return
    reply = build_lead_reply(
        message.text or "",
        settings.whatsapp_contact_link,
        settings.whatsapp_phone,
    )
    lead_service.store.record(
        message.from_user, message.text or "", reply.stage, reply.lead_score, reply.summary
    )
    await message.answer(reply.text)
    if reply.is_hot and settings.owner_telegram_id is not None:
        await message.bot.send_message(
            settings.owner_telegram_id,
            hot_lead_notification(message, reply),
        )
