from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from app.comment_discovery import comment_discovery
from app.config import Settings
from app.handlers.agents import arg_text
from app.handlers.sales import require_owner

router = Router()


@router.message(Command("comment_discovery_status"))
async def comment_discovery_status(message: Message, settings: Settings):
    await message.answer(
        "Safe Comment Discovery status\n"
        f"discovery enabled: {str(settings.comment_discovery_enabled).lower()}\n"
        f"auto reply enabled: {str(settings.comment_auto_reply_enabled).lower()}\n"
        f"approval required: {str(settings.comment_approval_required).lower()}\n"
        f"daily limit: {settings.comment_daily_limit}\n"
        f"comments posted today: {comment_discovery.posted_today()}\n"
        f"drafts in queue: {len(comment_discovery.drafts())}\n"
        f"search topics: {settings.comment_search_topics}\n"
        f"min relevance score: {settings.comment_min_relevance_score}\n"
        f"last discovery action: {comment_discovery.last_action}\n"
        f"last error: {comment_discovery.last_error or 'none'}"
    )


@router.message(Command("comment_find"))
async def comment_find(message: Message, settings: Settings):
    text = arg_text(message)
    if not text:
        await message.answer(
            "Официальный источник поиска Threads не подключён. Вставьте текст или ссылку "
            "на ветку после команды — агент безопасно оценит её и подготовит drafts."
        )
        return
    added, reason = comment_discovery.add_source(text, settings)
    await message.answer(
        f"Найдено/передано веток: 1\nПринято в queue: {1 if added else 0}\n"
        f"Создано комментариев: {added}\nОтклонено: {0 if added else 1}\nПричина: {reason}"
    )


@router.message(Command("comment_generate"))
async def comment_generate(message: Message):
    comments = comment_discovery.generate_comments(arg_text(message))
    if not comments:
        await message.answer("Тема нерелевантна или рискованна: безопасные комментарии не созданы.")
        return
    await message.answer("\n\n".join(f"{i}. {text}" for i, text in enumerate(comments, 1)))


@router.message(Command("comment_queue"))
async def comment_queue(message: Message):
    drafts = comment_discovery.drafts()
    if not drafts:
        await message.answer("Очередь комментариев пуста.")
        return
    await message.answer("\n\n".join(
        f"#{item.id} · {item.summary}\nrelevance: {item.relevance_score} · risk: {item.risk_score}\n"
        f"{item.comment}\nПочему уместен: {item.rationale}"
        for item in drafts[:10]
    ))


@router.message(Command("comment_next"))
async def comment_next(message: Message):
    item = next(iter(comment_discovery.drafts()), None)
    if not item:
        await message.answer("Draft-комментариев нет.")
        return
    await message.answer(
        f"Комментарий #{item.id}\nИсточник: {item.summary}\n\n{item.comment}\n\n"
        f"✅ /comment_publish {item.id}\n❌ /comment_skip {item.id}\n"
        f"🔁 /comment_generate {item.source}"
    )


@router.message(Command("comment_publish"))
async def comment_publish(message: Message, settings: Settings):
    if not await require_owner(message, settings):
        return
    item_id = arg_text(message)
    ok, result = comment_discovery.publish(item_id, settings, owner_confirmed=True)
    await message.answer(result)


@router.message(Command("comment_skip"))
async def comment_skip(message: Message, settings: Settings):
    if not await require_owner(message, settings):
        return
    item = next((x for x in comment_discovery.items if x.id == arg_text(message)), None)
    if not item:
        await message.answer("Комментарий не найден.")
        return
    item.status = "skipped"
    await message.answer("Комментарий пропущен.")


@router.message(Command("comment_report"))
async def comment_report(message: Message):
    await message.answer(
        "Safe Comment Discovery report\n"
        f"Найдено веток/источников: {comment_discovery.found_count}\n"
        f"Подготовлено комментариев: {len(comment_discovery.items)}\n"
        f"Опубликовано сегодня: {comment_discovery.posted_today()}\n"
        f"Ожидают подтверждения: {len(comment_discovery.drafts())}\n"
        f"Ошибки: {comment_discovery.last_error or 'нет'}"
    )
