from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery
from app.agents import (
    AGENTS,
    agents_help,
    build_prompt,
    fallback_posts,
    fallback_threads_day_posts,
    POSITIONING_TEXT,
    safe_threads_post,
    viral_niche_post,
    viral_threads_day_posts,
)
from app.content_safety import validate_threads_post
from app.config import Settings
from app.keyboards import threads_post_keyboard
from app.ollama_client import ask_ollama, build_ollama_options, test_ollama
from app.post_queue import post_queue, QueuedPost
from app.threads_client import ThreadsClient
from app.threads_growth import (
    add_strong_unique_post,
    best_publishable_post,
    next_unique_publishable_post,
    purge_duplicate_drafts,
    has_strong_cta,
    is_senior_marketing_post,
    refill_growth_queue,
    viral_fallback,
    metadata_for_text,
    queue_smm_quality,
    rebuild_growth_queue,
    angle_is_blocked,
)
from app.comment_discovery import comment_discovery
from app.growth_state import growth_runtime
from app.handlers.sales import require_owner
from datetime import datetime, timezone

router = Router()
EMPTY_HELP = "Добавьте текст после команды. Пример:\n{example}"
UNKNOWN_COMMAND = "Неизвестная команда. Напишите /agents, чтобы посмотреть список агентов."
OPTIONAL_TEXT_COMMANDS = {"/posts", "/niches"}
COPY_REQUESTS = ("скопируй полностью", "сделай точно как он", "один в один")


def arg_text(message: Message) -> str:
    parts = (message.text or "").split(maxsplit=1)
    return parts[1].strip() if len(parts) > 1 else ""


async def generate_posts_response(settings: Settings, niche: str) -> str:
    # Для маленькой модели qwen2.5:0.5b /posts использует deterministic fallback,
    # чтобы не зависать на Railway.
    fallback = fallback_posts()
    return "\n\n".join(f"{index}. {post}" for index, post in enumerate(fallback, 1))


def profile_copy_refusal(text: str) -> str | None:
    if any(phrase in (text or "").lower() for phrase in COPY_REQUESTS):
        return (
            "Я могу разобрать механику и адаптировать стиль под вашу нишу, "
            "но не буду копировать чужой текст дословно."
        )
    return None


def profile_analysis(text: str, mode: str) -> str:
    refusal = profile_copy_refusal(text)
    if refusal:
        return refusal
    subject = (text or "").strip()[:300] or "профиль без описания"
    if mode == "posts":
        return (
            f"Механика источника: {subject}\n\n"
            "1. Потерянная заявка редко выглядит как потеря.\n\nAI-бот фиксирует первый "
            "контакт и передаёт его в CRM.\n\nНапишите «аудит» в личку — покажу точки потерь.\n\n"
            "2. Direct — не CRM. AI-администратор отвечает сразу, уточняет запрос и не "
            "даёт лиду исчезнуть.\n\nНапишите «бот» — покажу схему под вашу нишу."
        )
    if mode == "strategy":
        return (
            "Стратегия адаптации: сохранить частоту хуков и короткие абзацы, но заменить "
            "чужие формулировки на боли заявок, Direct, CRM и follow-up. Контент-микс: "
            "40% боли, 30% разборы, 20% кейсовая механика, 10% CTA."
        )
    return (
        f"Анализ механики профиля: {subject}\n"
        "Сильные элементы: короткий хук, одна боль, конкретное последствие, ясный следующий шаг.\n"
        "Адаптация: AI-чат-боты, обработка заявок, Direct/Telegram/WhatsApp, CRM и follow-up.\n"
        "Чужие тексты и личность автора дословно не копируются."
    )


def get_command_name(command) -> str:
    command_name = command.command if hasattr(command, "command") else str(command)
    if not command_name.startswith("/"):
        command_name = f"/{command_name}"
    return command_name


async def run_prompt(message: Message, settings: Settings, command: str, text: str):
    command_name = get_command_name(command)
    if command_name not in AGENTS:
        await message.answer(UNKNOWN_COMMAND)
        return
    if not text and command_name not in OPTIONAL_TEXT_COMMANDS:
        await message.answer(EMPTY_HELP.format(example=AGENTS[command_name].example))
        return
    if command_name == "/posts":
        await message.answer("Готовлю 10 постов...")
        await message.answer(await generate_posts_response(settings, text))
        return
    await message.answer("Готовлю ответ через Ollama...")
    try:
        await message.answer(await ask_ollama(settings, build_prompt(command_name, text)))
    except RuntimeError as e:
        await message.answer(str(e))

@router.message(Command("agents"))
async def cmd_agents(message: Message): await message.answer(agents_help())


for _profile_command, _profile_mode in {
    "profile_scan": "scan",
    "profile_style": "scan",
    "profile_strategy": "strategy",
    "profile_posts": "posts",
    "profile_hooks": "scan",
    "profile_compare": "strategy",
}.items():
    async def profile_handler(message: Message, mode=_profile_mode):
        await message.answer(profile_analysis(arg_text(message), mode))
    router.message(Command(_profile_command))(profile_handler)

for _cmd in [c.lstrip("/") for c in AGENTS]:
    async def handler(message: Message, settings: Settings, command=_cmd):
        await run_prompt(message, settings, command, arg_text(message))
    router.message(Command(_cmd))(handler)

@router.message(Command("day"))
async def cmd_day(message: Message, settings: Settings):
    prompt = """Сделай план дня продаж AI-чат-ботов. Формат строго:
1. 5 постов
2. 5 hooks
3. 3 идеи Threads
4. 10 идей комментариев
5. 5 сообщений в личку
6. Оффер дня
7. Ниша дня
8. План действий на день
9. Follow-up для старых диалогов
10. Что сегодня отправлять потенциальным клиентам
Русский язык, коротко, без спама, без автоличек, все отправки вручную после подтверждения пользователя."""
    await message.answer("Готовлю день продаж через Ollama...")
    try: await message.answer(await ask_ollama(settings, prompt))
    except RuntimeError as e: await message.answer(str(e))


def render_post(post: QueuedPost) -> str:
    meta = metadata_for_text(post.text)
    rubric = post.rubric or meta["rubric"]
    angle = post.content_angle or meta["content_angle"]
    goal = post.goal or meta["goal"]
    cta = post.cta_type or meta["cta_type"]
    stage = "прогрев" if goal not in ("Offer", "продажа") else "оффер"
    why = "показывает живую экспертизу, даёт пользу до CTA и двигает аккаунт к подписчикам, доверию и заявкам"
    return (
        f"Threads draft #{post.id}\nСтатус: {post.status}\n"
        f"Goal: {goal}\nFormat: {rubric}\nAngle: {angle}\nStage: {stage}\nCTA: {cta}\n"
        f"Why this post matters: {why}.\n\n{post.text}\n\nПубликация только после подтверждения."
    )

async def show_post(message_or_cb, post: QueuedPost):
    if isinstance(message_or_cb, CallbackQuery):
        await message_or_cb.message.answer(render_post(post), reply_markup=threads_post_keyboard(post.id))
    else:
        await message_or_cb.answer(render_post(post), reply_markup=threads_post_keyboard(post.id))

def queue_safe_post(text: str, *, fallback: str, source: str) -> QueuedPost | None:
    # Every generated draft uses the same quality and duplicate gate. The fallback
    # argument remains for compatibility with existing command call sites.
    candidate = text if validate_threads_post(text)[0] else fallback
    return add_strong_unique_post(post_queue, candidate, source=source)


def queue_viral_post(text: str, *, source: str, index: int = 0, niche: str | None = None) -> QueuedPost | None:
    return add_strong_unique_post(
        post_queue, text, source=source, fallback_index=index, niche=niche,
    )

@router.message(Command("threads_day"))
async def threads_day(message: Message, settings: Settings):
    posts = viral_threads_day_posts()[:5] if settings.threads_viral_only else fallback_threads_day_posts()[:5]
    queued = []
    for index, post in enumerate(posts):
        queued_post = (
            queue_viral_post(post, source="threads-day-viral", index=index)
            if settings.threads_viral_only
            else queue_safe_post(post, fallback=fallback_threads_day_posts()[index], source="threads-day")
        )
        if queued_post:
            queued.append(queued_post)
    await message.answer(f"Добавил в очередь: {len(queued)} постов.")
    if queued: await show_post(message, queued[0])

@router.message(Command("threads_post"))
async def threads_post(message: Message, settings: Settings):
    topic = arg_text(message)
    if not topic: await message.answer("Добавьте тему после команды. Пример:\n/threads_post AI-бот для салона красоты"); return
    if settings.threads_viral_only:
        post = queue_viral_post(viral_niche_post(topic), source="threads-post-viral", niche=topic)
    else:
        text = safe_threads_post(topic)
        post = queue_safe_post(text, fallback=safe_threads_post("обработка заявок"), source="threads-post")
    if post:
        await show_post(message, post)
    else:
        await message.answer("Уникальный draft не добавлен: похожий пост уже есть в очереди.")

@router.message(Command("viral_threads_day"))
async def viral_threads_day(message: Message):
    posts = viral_threads_day_posts()
    queued = [
        queued_post for index, post in enumerate(posts)
        if (queued_post := queue_viral_post(post, source="viral-threads-day", index=index))
    ]
    await message.answer(f"Добавил в очередь: {len(queued)} viral draft-постов.")
    if queued:
        await show_post(message, queued[0])

@router.message(Command("viral_post"))
async def viral_post(message: Message):
    niche = arg_text(message)
    if not niche:
        await message.answer("Добавьте нишу после команды. Пример:\n/viral_post клиники")
        return
    post = queue_viral_post(viral_niche_post(niche), source="viral-post", niche=niche)
    if post:
        await show_post(message, post)
    else:
        await message.answer("Уникальный draft не добавлен: похожий пост уже есть в очереди.")


@router.message(Command("growth_status"))
async def growth_status(message: Message, settings: Settings):
    today = datetime.now(timezone.utc).date()
    await message.answer(
        f"autopilot enabled: {'yes' if growth_runtime.enabled(settings.growth_autopilot_enabled) else 'no'}\n"
        f"THREADS_GROWTH_MODE_ENABLED={str(settings.threads_growth_mode_enabled).lower()}\n"
        f"THREADS_MIN_QUEUE_SIZE={settings.threads_min_queue_size}\n"
        f"THREADS_VIRAL_ONLY={str(settings.threads_viral_only).lower()}\n"
        f"draft count: {post_queue.get_draft_count()}\n"
        f"published today: {post_queue.get_published_count_for_date(today)}\n"
        f"next post hours: {','.join(map(str, settings.threads_auto_post_hours))}\n"
        f"auto_generate_if_queue_empty: {str(settings.threads_auto_generate_if_queue_empty).lower()}\n"
        f"auto_publish: {str(settings.threads_auto_publish).lower()}\n"
        f"daily report enabled: {str(settings.growth_daily_report_enabled).lower()}\n"
        f"last autopilot action: {growth_runtime.last_action}\n"
        f"last autopilot error: {growth_runtime.last_error or 'none'}\n"
        f"Safe Comment Discovery: {'enabled' if settings.comment_discovery_enabled else 'disabled'}, "
        f"drafts={len(comment_discovery.drafts())}, approval={settings.comment_approval_required}"
    )


def build_growth_report(settings: Settings) -> str:
    today = datetime.now(timezone.utc).date()
    published = [p for p in post_queue.list_by_status("published") if (p.published_at or "").startswith(today.isoformat())]
    last_duplicate = post_queue.get_last_duplicate_skip()
    last_duplicate_text = (last_duplicate or {}).get("text", "")[:80] if last_duplicate else "нет"
    posts_lead_to_dm = bool(published) and all(has_strong_cta(p.text) for p in published)
    weak_positioning_risk = bool(published) and not all(is_senior_marketing_post(p.text) for p in published)
    q = queue_smm_quality(post_queue)
    return (
        "AI Growth Manager — growth report\n"
        f"Опубликовано сегодня: {len(published)}\n"
        f"Посты: {', '.join('#' + p.id for p in published) or 'нет'}\n"
        f"Draft в очереди: {post_queue.get_draft_count()}\n"
        f"Добавлено автопилотом: {growth_runtime.posts_added}\n"
        f"duplicate skipped today: {post_queue.get_duplicate_skipped_count_for_date(today)}\n"
        f"last duplicate skipped: {last_duplicate_text}\n"
        f"Threads API errors: {growth_runtime.last_error or 'нет'}\n"
        "Лиды/hot leads: обрабатываются Sales DM Agent\n"
        f"Ollama: модель {settings.ollama_model}, fallback-first активен\n"
        f"WhatsApp handoff: {'настроен' if settings.whatsapp_contact_link or settings.whatsapp_phone else 'не настроен'}\n"
        f"Last autopilot action: {growth_runtime.last_action}\n"
        f"Last autopilot error: {growth_runtime.last_error or 'нет'}\n\n"
        "Marketing quality:\n"
        "• позиционирование: AI-боты / заявки / CRM\n"
        "• оффер дня: найду точки потери заявок и покажу, какой AI-бот их закроет\n"
        f"• посты сегодня ведут к личке: {'yes' if posts_lead_to_dm else 'no'}\n"
        f"• есть риск слабого позиционирования: {'yes' if weak_positioning_risk else 'no'}\n\n"
        "SMM quality:\nSMM Director Report:\n"
        f"• форматов в очереди: {q['formats_count']}\n"
        f"• уникальных angles в очереди: {q['unique_angles']}\n"
        f"• повторяющиеся angles: {', '.join(q['repeated_angles']) if q['repeated_angles'] else 'none'}\n"
        f"• рубрики в очереди: {', '.join(q['rubrics']) or 'none'}\n"
        f"• CTA повторяется: {'yes' if q['cta_diversity'] == 'weak' else 'no'}\n"
        f"• банальные посты: {q['banal_count']}\n"
        f"• есть посты на доверие: {'yes' if q['has_trust'] else 'no'}\n"
        f"• есть посты на оффер: {'yes' if q['has_offer'] else 'no'}\n"
        f"• есть посты на экспертность: {'yes' if q['has_expertise'] else 'no'}\n"
        f"• посты не выглядят одинаково: {'yes' if q['look_unique'] else 'no'}\n"
        f"• риск роботности: {q['template_risk']}\n"
        f"• рекомендация SMM-директора: {'Рекомендация: выполнить /growth_rebuild.' if q['template_risk'] == 'high' else ('Если очередь однотипная — нажмите /growth_rebuild.' if q['template_risk'] == 'medium' else 'держать микс форматов, angles и целей')}\n\n"
        "Safe Comment Discovery:\n"
        f"Найдено веток/источников: {comment_discovery.found_count}\n"
        f"Comment drafts создано: {len(comment_discovery.items)}\n"
        f"Опубликовано: {comment_discovery.posted_today()}\n"
        f"Ждут подтверждения: {len(comment_discovery.drafts())}"
    )


@router.message(Command("growth_report"))
async def growth_report(message: Message, settings: Settings):
    await message.answer(build_growth_report(settings))


@router.message(Command("autopilot_status"))
async def autopilot_status(message: Message, settings: Settings):
    today = datetime.now(timezone.utc).date()
    await message.answer(
        "Safe Autopilot status\n"
        f"autopilot enabled: {'yes' if growth_runtime.enabled(settings.growth_autopilot_enabled) else 'no'}\n"
        f"growth mode enabled: {'yes' if settings.threads_growth_mode_enabled else 'no'}\n"
        f"viral only: {'yes' if settings.threads_viral_only else 'no'}\n"
        f"min queue size: {settings.threads_min_queue_size}\n"
        f"draft count: {post_queue.get_draft_count()}\n"
        f"published today: {post_queue.get_published_count_for_date(today)}\n"
        f"next post hours: {','.join(map(str, settings.threads_auto_post_hours))}\n"
        f"auto publish: {'yes' if settings.threads_auto_publish else 'no'}\n"
        f"auto generate if queue empty: {'yes' if settings.threads_auto_generate_if_queue_empty else 'no'}\n"
        f"daily report enabled: {'yes' if settings.growth_daily_report_enabled else 'no'}\n"
        f"last autopilot action: {growth_runtime.last_action}\n"
        f"last autopilot error: {growth_runtime.last_error or 'none'}\n"
        "DM agent status: enabled\n"
        f"WhatsApp status: {'configured' if settings.whatsapp_contact_link or settings.whatsapp_phone else 'not configured'}\n\n"
        "Safe Comment Discovery:\n"
        f"enabled: {'yes' if settings.comment_discovery_enabled else 'no'}\n"
        f"approval required: {'yes' if settings.comment_approval_required else 'no'}\n"
        f"drafts: {len(comment_discovery.drafts())}, posted today: {comment_discovery.posted_today()}"
    )


@router.message(Command("autopilot_on"))
async def autopilot_on(message: Message, settings: Settings):
    if not await require_owner(message, settings):
        return
    growth_runtime.autopilot_override = True
    growth_runtime.last_action = "автопилот включён владельцем"
    await message.answer(
        "Safe Autopilot включён в runtime. Для постоянного включения установите "
        "GROWTH_AUTOPILOT_ENABLED=true в Railway Variables."
    )


@router.message(Command("autopilot_off"))
async def autopilot_off(message: Message, settings: Settings):
    if not await require_owner(message, settings):
        return
    growth_runtime.autopilot_override = False
    growth_runtime.last_action = "автопилот выключен владельцем"
    await message.answer(
        "Safe Autopilot выключен в runtime. Для постоянного выключения установите "
        "GROWTH_AUTOPILOT_ENABLED=false в Railway Variables."
    )


@router.message(Command("growth_refill"))
async def growth_refill(message: Message, settings: Settings):
    added = refill_growth_queue(post_queue, settings.threads_min_queue_size, source="growth-refill-command")
    growth_runtime.posts_added += len(added)
    growth_runtime.last_action = f"очередь пополнена на {len(added)} постов"
    rubrics = sorted({p.rubric or metadata_for_text(p.text)["rubric"] for p in added})
    angles = sorted({p.content_angle or metadata_for_text(p.text)["content_angle"] for p in added})
    await message.answer(
        f"Очередь пересобрана как SMM-контент-план.\n"
        f"Добавлено: {len(added)}\n"
        f"Форматы: {', '.join(rubrics) or 'нет'}\n"
        f"Angles: {', '.join(angles) or 'нет'}\n"
        f"Отклонено как банальное: 0\n"
        f"Отклонено как повтор angle: {post_queue.get_duplicate_skipped_count_for_date(datetime.now(timezone.utc).date())}\n"
        f"Дубли/повторы отклонены: {post_queue.get_duplicate_skipped_count_for_date(datetime.now(timezone.utc).date())}\n"
        f"Сейчас draft в очереди: {post_queue.get_draft_count()}."
    )



@router.message(Command("growth_rebuild"))
async def growth_rebuild(message: Message, settings: Settings):
    result = rebuild_growth_queue(post_queue, settings.threads_min_queue_size, source="growth-rebuild-command")
    growth_runtime.posts_added += int(result["added"])
    growth_runtime.last_action = f"очередь пересобрана, добавлено {result['added']}"
    await message.answer(
        "Очередь пересобрана.\n"
        f"Удалено шаблонных: {result['removed_banal']}\n"
        f"Удалено повторов angle: {result['removed_angle']}\n"
        f"Удалено дублей: {result['removed_duplicates']}\n"
        f"Добавлено новых: {result['added']}\n"
        f"Риск однотипности: {result['robot_like_risk']}\n"
        f"Итоговые formats: {', '.join(result['rubrics'])}\n"
        f"Итоговые angles: {', '.join(result['angles'])}"
    )

@router.message(Command("growth_plan"))
async def growth_plan(message: Message):
    await message.answer(
        "План роста Threads на сегодня:\n\n"
        "1. Главный маркетинговый фокус дня:\nЦель дня: набрать доверие и привести людей в личку на аудит заявок.\n\n"
        "2. Контент на день:\n"
        "10:00 — Expert Insight: почему заявки теряются между Direct и CRM\n"
        "14:00 — Case-style: как салон теряет клиентов на записи\n"
        "18:00 — Direct CTA: аудит пути заявки\n\n"
        "3. Рубрики сегодня:\n- экспертность\n- кейс\n- оффер\n\n"
        "4. Что НЕ повторяем:\n- не используем снова “админ ответил через 2 часа”\n- не повторяем вчерашний CTA\n- не пишем про сайты/лендинги\n\n"
        "5. Главный оффер дня / CTA дня:\n“Напишите «аудит» — покажу, где теряются заявки.”\n\n"
        "6. Ожидаемый результат:\nбольше входящих сообщений по словам “аудит”, “бот”, “разбор”."
    )


@router.message(Command("engagement_tasks"))
async def engagement_tasks(message: Message):
    await message.answer(
        "Автопилот уже ведёт постинг сам. Ниже — необязательные безопасные действия, если хотите усилить охват вручную.\n"
        "1. Найти 5 свежих постов про заявки, продажи, Direct или работу администраторов.\n"
        "2. Оставить 5 комментариев из готовых вариантов в /growth_plan.\n"
        "3. Ответить на 3 релевантные ветки.\n"
        "4. Проверить входящие и незавершённые диалоги.\n"
        "5. Убедиться, что очередь заполнена.\n"
        "6. CTA дня: «аудит».\n\n"
        "Все действия выполняются вручную: без автолайков, автофолловинга и автокомментариев."
    )

@router.message(Command("positioning"))
async def positioning(message: Message):
    await message.answer(POSITIONING_TEXT)

@router.message(Command("threads_queue"))
async def threads_queue(message: Message):
    purge_duplicate_drafts(post_queue)
    posts = post_queue.list_posts()
    if not posts: await message.answer("Очередь Threads пустая."); return
    lines = []
    for p in posts:
        if p.status == "skipped" and p.error_reason == "duplicate":
            continue
        meta = metadata_for_text(p.text)
        lines.append(
            f"#{p.id} — {p.status}\n"
            f"Rubric: {p.rubric or meta['rubric']}\n"
            f"Angle: {p.content_angle or meta['content_angle']}\n"
            f"Niche: {p.niche or meta['niche']}\n"
            f"CTA: {p.cta_type or meta['cta_type']}\n"
            f"Preview: {p.text[:90]}"
        )
    await message.answer("\n\n".join(lines))

@router.message(Command("health"))
async def health(message: Message, settings: Settings):
    today = datetime.now(timezone.utc).date()
    await message.answer(
        "✅ Бот работает\n"
        f"Модель Ollama: {settings.ollama_model}\n"
        f"Ollama URL: {settings.ollama_base_url}\n"
        f"Threads API настроен: {'yes' if settings.threads_api_configured else 'no'}\n"
        f"Автопостинг включен: {'yes' if settings.threads_auto_posting_enabled else 'no'}\n"
        f"Часы публикаций: {','.join(map(str, settings.threads_auto_post_hours))}\n"
        f"Дневной лимит: {settings.threads_daily_post_limit}\n"
        f"Опубликовано сегодня: {post_queue.get_published_count_for_date(today)}\n"
        f"Draft-постов: {post_queue.get_draft_count()}\n"
        "/ollama_test — проверить связь с Ollama"
    )

@router.message(Command("ollama_test"))
async def ollama_test(message: Message, settings: Settings):
    ok, result = await test_ollama(settings)
    options = build_ollama_options(settings)
    status = "работает" if ok else "ошибка"
    details = f"ответ: {result}" if ok else f"ошибка: {result}"
    await message.answer(
        f"OLLAMA_BASE_URL: {settings.ollama_base_url}\n"
        f"OLLAMA_MODEL: {settings.ollama_model}\n"
        f"options: {options}\n"
        f"статус: {status}\n"
        f"{details}"
    )

@router.message(Command("autopost_status"))
async def autopost_status(message: Message, settings: Settings):
    await message.answer(
        f"Автопостинг: {'включен' if settings.threads_auto_posting_enabled else 'выключен'}\n"
        f"Постов в день: {settings.threads_auto_posts_per_day}\n"
        f"Часы: {','.join(map(str, settings.threads_auto_post_hours))}\n"
        f"Timezone: {settings.threads_auto_post_timezone}\n"
        f"Лимит в день: {settings.threads_daily_post_limit}"
    )

@router.message(Command("autopost_on"))
async def autopost_on(message: Message):
    await message.answer("Включите THREADS_AUTO_POSTING_ENABLED=true в Railway Variables и перезапустите сервис.")

@router.message(Command("autopost_off"))
async def autopost_off(message: Message):
    await message.answer("Выключите THREADS_AUTO_POSTING_ENABLED=false в Railway Variables и перезапустите сервис.")

@router.message(Command("autopost_plan"))
async def autopost_plan(message: Message, settings: Settings):
    await message.answer(f"План автопостинга: {settings.threads_auto_posts_per_day} постов/день в часы {settings.threads_auto_post_hours} ({settings.threads_auto_post_timezone}).")

@router.message(Command("autopost_now"))
async def autopost_now(message: Message, settings: Settings):
    post = next_unique_publishable_post(post_queue)
    if not post: await message.answer("Нет постов для публикации: drafts дублируют published history или очередь пуста."); return
    await publish_by_id(message, settings, post.id)

@router.message(Command("autopost_generate"))
async def autopost_generate(message: Message, settings: Settings):
    await threads_day(message, settings)

async def publish_by_id(message: Message, settings: Settings, pid):
    post = post_queue.get_post(pid)
    if not post: await message.answer("Пост не найден."); return
    duplicate = post_queue.find_duplicate_for_publish(post.id, post.text)
    if duplicate:
        post_queue.mark_duplicate_skipped(post.id, reason=f"duplicate of published #{duplicate.id}")
        growth_runtime.last_error = f"duplicate skipped #{post.id}"
        await message.answer("Пост не опубликован: похожий пост уже был опубликован за последние 7 дней.")
        return
    meta = metadata_for_text(post.text)
    if angle_is_blocked(post_queue, post.content_angle or meta["content_angle"], exclude_id=post.id):
        post_queue.mark_duplicate_skipped(post.id, reason="angle repeated inside 48h or queue")
        await message.answer("Пост не опубликован: этот content_angle уже был недавно или слишком часто в очереди.")
        return
    is_valid, reason = validate_threads_post(post.text)
    if not is_valid:
        post_queue.mark_failed(post.id, f"safety: {reason}")
        await message.answer(f"Пост не опубликован: {reason}. Создайте новый premium draft.")
        return
    try:
        post_queue.approve_post(pid)
        result = await ThreadsClient(settings).publish_text_post(post.text)
        post_queue.mark_published(pid)
        await message.answer(f"Опубликовано в Threads. Ответ API: {result}")
    except RuntimeError as e: await message.answer(str(e))

@router.message(Command("threads_publish"))
async def threads_publish(message: Message, settings: Settings):
    text = arg_text(message)
    if not text or not text.isdigit(): await message.answer("Добавьте id поста. Пример:\n/threads_publish 1"); return
    await publish_by_id(message, settings, text)

@router.message(Command("threads_skip"))
async def threads_skip(message: Message):
    text=arg_text(message)
    if not text or not text.isdigit(): await message.answer("Добавьте id поста. Пример:\n/threads_skip 1"); return
    post = post_queue.skip_post(text); await message.answer("Пост пропущен." if post else "Пост не найден.")

@router.message(Command("threads_rewrite"))
async def threads_rewrite(message: Message, settings: Settings):
    text=arg_text(message)
    if not text or not text.isdigit(): await message.answer("Добавьте id поста. Пример:\n/threads_rewrite 1"); return
    post=post_queue.get_post(text)
    if not post: await message.answer("Пост не найден."); return
    fallback = safe_threads_post(post.text)
    try:
        new_text = await ask_ollama(settings, f"Переделай Threads-пост: короче, живее, без спама, с мягким CTA.\n\n{post.text}")
        rewritten = safe_threads_post(post.text, new_text)
    except RuntimeError:
        rewritten = fallback
    await show_post(message, post_queue.update_post(post.id, rewritten))

@router.message(Command("threads_next"))
async def threads_next(message: Message):
    post = post_queue.get_next_draft()
    if not post: await message.answer("Draft-постов нет."); return
    await show_post(message, post)

@router.callback_query(F.data.startswith("threads:"))
async def threads_callback(callback: CallbackQuery, settings: Settings):
    parts = callback.data.split(":")
    action = parts[1]
    pid = parts[2] if len(parts) > 2 else None
    if action == "publish" and pid: await publish_by_id(callback.message, settings, pid)
    elif action == "skip" and pid:
        post_queue.skip_post(pid); await callback.message.answer("Пост пропущен.")
    elif action == "rewrite" and pid:
        post = post_queue.get_post(pid)
        if post:
            fallback = safe_threads_post(post.text)
            try:
                new_text = await ask_ollama(settings, f"Переделай Threads-пост короче и живее:\n{post.text}")
                rewritten = safe_threads_post(post.text, new_text)
            except RuntimeError:
                rewritten = fallback
            await show_post(callback, post_queue.update_post(pid, rewritten))
    elif action == "next":
        post = post_queue.get_next_draft(); await show_post(callback, post) if post else await callback.message.answer("Draft-постов нет.")
    await callback.answer()
