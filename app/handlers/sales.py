from aiogram import F, Router
from aiogram.filters import Command, CommandStart
from aiogram.types import Message
from app.config import Settings
from app.lead_agent import HOT_LEAD_THRESHOLD, PRICE_RANGES, build_lead_reply, hot_lead_notification
from app.lead_store import LeadConversationService
from app.lead_hunter import lead_hunter_reply_notification
from app.client_acquisition import build_client_reply, has_inbound_signal

router = Router()

START_TEXT = """🚀 AI Growth Marketer

Я веду твой Threads-аккаунт как маркетолог, SMM и sales-ассистент.

Моя цель — растить доверие, находить клиентов и приводить заявки на AI-ботов.

Что я делаю каждый день:
📝 Пишу и публикую посты
💬 Ищу ветки и готовлю комментарии
🔎 Нахожу потенциальных клиентов
🤝 Готовлю первые сообщения
🔥 Помогаю доводить горячих лидов до заявки
📊 Вечером даю отчёт

🎯 Получение клиентов:
• /offer_post — пост на входящие заявки
• /audit_offer — оффер, био и закреп
• /profile_offer — оформить профиль
• /client_reply текст — ответ потенциальному клиенту

Главное меню:
📊 /today — отчёт за сегодня
🧠 /plan — план на день
📝 /content — посты и контент
🔎 /leads — клиенты и лиды
💬 /sales — продажи и ответы
🤖 /agent_status — автономный Threads-агент
📊 /agent_report — отчёт автономного агента
⚙️ /status — статус автопилота
🛠 /system — здоровье системы

Что делать каждый день:
1. Утром нажми /plan
2. Днём смотри /agent_status, /content и /leads
3. Если клиент ответил — вставь сообщение в /sales
4. Вечером смотри /today
"""

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


@router.message(Command("client_reply"))
async def client_reply_sales(message: Message):
    parts = (message.text or "").split(maxsplit=1)
    if len(parts) < 2 or not parts[1].strip():
        await message.answer("Добавьте сообщение клиента. Пример:\n/client_reply Сколько стоит бот?")
        return
    await message.answer(build_client_reply(parts[1].strip()))

@router.message(Command("sales"))
async def sales_menu(message: Message):
    await message.answer(
        "💬 Продажи\n\n"
        "Команды:\n"
        "• /sales_preview текст — проверить ответ клиенту\n"
        "• /dm_preview текст — DM-ответ\n"
        "• /client_reply текст — ответ потенциальному клиенту\n"
        "• /sales_status — статус продаж\n"
        "• /whatsapp_status — WhatsApp handoff\n\n"
        "Что дальше:\n1. Вставь сообщение клиента в /sales_preview\n2. Если лид горячий — передай владельцу"
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
    if getattr(settings, "client_acquisition_mode_enabled", True) and has_inbound_signal(message.text or ""):
        await message.answer(build_client_reply(message.text or ""))
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
