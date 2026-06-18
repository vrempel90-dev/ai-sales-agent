from aiogram import F, Router
from aiogram.filters import Command, CommandStart
from aiogram.types import Message
from app.config import Settings
from app.lead_agent import build_lead_reply, hot_lead_notification
from app.lead_store import LeadConversationService

router = Router()

START_TEXT = """Привет. Я AI Growth Manager для Threads в режиме Safe Autopilot.

Моя задача — вести профиль как команда специалистов: стратег, ghostwriter, growth-маркетолог, аналитик и sales-менеджер.

Я сам:
• создаю сильные Threads-посты, держу очередь и публикую по расписанию
• проверяю качество, сильные CTA и дубли
• готовлю безопасные комментарии к релевантным веткам
• веду лидов в личке и перевожу горячих клиентов в WhatsApp

Без автоспама, автолайков, автофолловинга и серых методов.

Safe Autopilot:
/autopilot_status · /autopilot_on · /autopilot_off
/growth_status · /growth_report · /growth_refill · /growth_plan
/engagement_tasks — необязательное ручное усиление

Threads:
/viral_threads_day · /viral_post ниша
/threads_queue · /threads_next · /threads_publish id

Safe Comment Discovery:
/comment_discovery_status · /comment_find текст_или_ссылка
/comment_queue · /comment_next · /comment_report

Profile Intelligence:
/profile_scan текст · /profile_strategy текст · /profile_posts текст

Sales DM и System:
/dm_preview сообщение · /whatsapp_status · /lead_mode_status
/health · /ollama_test · /autopost_status · /positioning

Legacy-команды сохранены для совместимости, но основной режим — AI Growth Manager."""

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
    lead_service.store.record(message.from_user, message.text or "", reply.stage)
    await message.answer(reply.text)
    if reply.is_hot and settings.owner_telegram_id is not None:
        await message.bot.send_message(
            settings.owner_telegram_id,
            hot_lead_notification(message),
        )
