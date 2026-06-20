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
from app.content_quality import evaluate_post
from app.threads_growth import (
    add_strong_unique_post,
    best_publishable_post,
    next_unique_publishable_post,
    ensure_active_post_quality,
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
from app.lead_hunter import add_candidate, lead_hunter, mark_skip, next_lead, prepare_send, run_autopilot_once, send_or_prepare, official_channel_available, SAFE_SOURCE_NOTE
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

@router.message(Command("content"))
async def content_menu(message: Message):
    await message.answer(
        "📝 Контент\n\n"
        "Команды:\n"
        "• /next_post — следующий пост\n"
        "• /posts — очередь постов\n"
        "• /refill — пополнить очередь\n"
        "• /rebuild — пересобрать очередь\n"
        "• /viral_post тема — пост на тему\n\n"
        "Что дальше:\n1. Проверь /next_post\n2. Если очередь слабая — нажми /rebuild"
    )

@router.message(Command("leads"))
async def leads_menu(message: Message):
    await message.answer(
        "🔎 Клиенты\n\n"
        "Команды:\n"
        "• /find_leads — найти клиентов\n"
        "• /next_lead — следующий лид\n"
        "• /lead_queue — очередь лидов\n"
        "• /lead_report — отчёт по лидам\n"
        "• /lead_scan текст — проверить клиента\n\n"
        "Что дальше:\n1. Проверь /next_lead\n2. Для нового профиля используй /lead_scan"
    )

@router.message(Command("find_leads"))
async def find_leads(message: Message):
    await message.answer(
        "🔎 Поиск клиентов\n\n"
        "Я безопасно работаю в режиме prepared/manual: без mass DM и fake sending.\n\n"
        "Что сделать:\n1. Найди бизнес-профиль в целевой нише\n2. Скопируй био/пост/описание\n3. Отправь: /lead_scan текст\n4. Лучший лид появится в /next_lead"
    )

@router.message(Command("system"))
async def system_menu(message: Message):
    await message.answer(
        "🛠 Система\n\n"
        "Команды:\n"
        "• /health — здоровье бота\n"
        "• /ollama_test — проверка модели\n"
        "• /autopilot_status — технический статус автопилота\n"
        "• /growth_report — полный growth-отчёт\n\n"
        "Что дальше:\n1. Если есть ошибка — начни с /health\n2. Для модели проверь /ollama_test"
    )


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
    rubric = post.content_format or post.rubric or meta["content_format"]
    angle = post.content_angle or meta["content_angle"]
    goal = post.goal or meta["goal"]
    cta = post.cta_type or meta["cta_type"]
    hook_type = post.hook_type or meta["hook_type"]
    pain = post.pain_angle or meta["pain_angle"]
    viral = post.viral_score or meta["viral_score"]
    quality = post.quality_score or meta["quality_score"]
    uniq = post.uniqueness_score or meta["uniqueness_score"]
    stage = "прогрев" if goal not in ("Offer", "продажа") else "оффер"
    why = "есть боль/деньги/сценарий, мягкий CTA и отличие по angle, hook, структуре и CTA"
    return (
        f"Threads draft #{post.id}\nСтатус: {post.status}\n"
        f"Goal: {goal}\nFormat: {rubric}\nAngle: {angle}\nStage: {stage}\n"
        f"hook type: {hook_type}\npain: {pain}\nCTA: {cta}\n"
        f"source: {post.generation_source or post.source or 'unknown'}\nfallback: {'yes' if post.fallback_used else 'no'}\n"
        f"viral_score: {viral}\nquality_score: {quality}\nuniqueness_score: {uniq}\n"
        f"Why this post matters: {why}.\nWhy this post can work: {why}.\n\n{post.text}\n\nПубликация только после подтверждения."
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



def render_lead_hunter_status(settings: Settings) -> str:
    lead_outreach_enabled = lead_hunter.enabled(
        getattr(settings, "lead_hunter_autopilot_enabled", False)
    )
    return (
        "Safe Lead Hunter Agent status\n"
        f"enabled: {'yes' if settings.lead_hunter_enabled else 'no'}\n"
        f"autopilot enabled: {'yes' if lead_outreach_enabled else 'no'}\n"
        f"auto DM enabled: {'yes' if settings.lead_hunter_auto_dm_enabled else 'no'}\n"
        f"approval required: {'yes' if settings.lead_hunter_approval_required else 'no'}\n"
        f"allowed channels: {getattr(settings, 'lead_hunter_allowed_channels', 'telegram')}\n"
        f"daily DM limit: {settings.lead_hunter_daily_dm_limit}\n"
        f"messages sent today: {lead_hunter.sent_today()}\n"
        f"leads in queue: {len(lead_hunter.drafts())}\n"
        f"min score: {settings.lead_hunter_min_score}\n"
        f"official channel available: {'yes' if any(official_channel_available(i, getattr(settings, 'lead_hunter_allowed_channels', 'telegram')) for i in lead_hunter.drafts()) else 'no'}\n"
        f"last action: {lead_hunter.last_action}\n"
        f"last error: {lead_hunter.last_error or 'нет'}\n"
        f"source mode: {SAFE_SOURCE_NOTE}"
    )

@router.message(Command("lead_hunter_status"))
async def lead_hunter_status(message: Message, settings: Settings):
    await message.answer(render_lead_hunter_status(settings))

@router.message(Command("lead_autopilot_status"))
async def lead_autopilot_status(message: Message, settings: Settings):
    await message.answer(render_lead_hunter_status(settings))

@router.message(Command("lead_autopilot_on"))
async def lead_autopilot_on(message: Message, settings: Settings):
    if not await require_owner(message, settings):
        return
    lead_hunter.autopilot_override = True
    lead_hunter.last_action = "lead outreach autopilot enabled by owner"
    note = "Для постоянного включения установите LEAD_HUNTER_AUTOPILOT_ENABLED=true в Railway Variables."
    if not any(official_channel_available(i, getattr(settings, 'lead_hunter_allowed_channels', 'telegram')) for i in lead_hunter.drafts()):
        note += "\nАвтопилот включить можно, но автоотправка невозможна без официального канала DM. Лиды будут переходить в ready_for_manual_send."
    await message.answer(note)

@router.message(Command("lead_autopilot_off"))
async def lead_autopilot_off(message: Message, settings: Settings):
    if not await require_owner(message, settings):
        return
    lead_hunter.autopilot_override = False
    lead_hunter.last_action = "lead outreach autopilot disabled by owner"
    await message.answer("Lead Outreach Autopilot выключен.")

@router.message(Command("lead_autopilot_run"))
async def lead_autopilot_run(message: Message, settings: Settings):
    ok, result = run_autopilot_once(
        enabled=getattr(settings, "lead_hunter_autopilot_enabled", False), min_score=settings.lead_hunter_min_score,
        daily_limit=settings.lead_hunter_daily_dm_limit, auto_dm_enabled=settings.lead_hunter_auto_dm_enabled,
        approval_required=settings.lead_hunter_approval_required, allowed_channels=getattr(settings, 'lead_hunter_allowed_channels', 'telegram'),
        require_personalization=getattr(settings, "lead_hunter_require_personalization", True),
        block_if_no_official_channel=getattr(settings, "lead_hunter_block_if_no_official_channel", True),
    )
    await message.answer(("Готово." if ok else "Не отправлено автоматически.") + "\n" + result)

@router.message(Command("lead_scan"))
async def lead_scan(message: Message, settings: Settings):
    text = arg_text(message)
    if not text:
        await message.answer("Добавьте текст профиля/био/поста. Пример:\n/lead_scan салон красоты, запись в Direct")
        return
    data, lead, status = add_candidate(text, settings.lead_hunter_min_score)
    next_step = "сохранён в outreach queue" if lead else ("не добавлен: дубль" if status == "duplicate" else "не добавлен: score ниже минимального")
    await message.answer(
        f"Niche: {data['niche']}\n"
        f"Lead score: {data['score']}\n"
        f"Pain hypothesis: {data['pain_hypothesis']}\n"
        f"Why suitable / not suitable: {data['why']}\n"
        f"Recommended first message:\n{data['draft_message']}\n\n"
        f"Next step: {next_step}"
    )

@router.message(Command("lead_queue"))
async def lead_queue_cmd(message: Message):
    items = lead_hunter.drafts()
    if not items:
        await message.answer("Lead outreach queue пустая.")
        return
    await message.answer("\n\n".join(f"#{i.id} — {i.niche}, score {i.score}, status {i.status}\nSource: {i.source_text[:90]}\nDraft: {i.draft_message}" for i in items))

@router.message(Command("lead_next", "next_lead"))
async def lead_next_cmd(message: Message):
    lead = next_lead()
    if not lead:
        await message.answer("Нет лидов в очереди.")
        return
    await message.answer(
        f"Lead #{lead.id}\nNiche: {lead.niche}\nScore: {lead.score}\nReason: {lead.reason}\n"
        f"Draft message:\n{lead.draft_message}\n\nRecommended next step: подтвердить и отправить вручную. Инструкция: /lead_send {lead.id} или отправить вручную."
    )

@router.message(Command("lead_send"))
async def lead_send_cmd(message: Message, settings: Settings):
    lead_id = arg_text(message)
    if not lead_id:
        await message.answer("Добавьте id. Пример: /lead_send abc123")
        return
    ok, result = prepare_send(
        lead_id, min_score=settings.lead_hunter_min_score, daily_limit=settings.lead_hunter_daily_dm_limit,
        approval_required=settings.lead_hunter_approval_required, auto_dm_enabled=settings.lead_hunter_auto_dm_enabled,
        allowed_channels=getattr(settings, 'lead_hunter_allowed_channels', 'telegram'), require_personalization=getattr(settings, "lead_hunter_require_personalization", True),
        block_if_no_official_channel=getattr(settings, "lead_hunter_block_if_no_official_channel", True),
    )
    await message.answer(("Отправлено." if ok else "Не отправлено автоматически.") + "\n" + result)

@router.message(Command("lead_confirm_send"))
async def lead_confirm_send_cmd(message: Message, settings: Settings):
    if not await require_owner(message, settings):
        return
    lead_id = arg_text(message)
    if not lead_id:
        await message.answer("Добавьте id. Пример: /lead_confirm_send abc123")
        return
    ok, result = send_or_prepare(
        lead_id, min_score=settings.lead_hunter_min_score, daily_limit=settings.lead_hunter_daily_dm_limit,
        approval_required=False, auto_dm_enabled=settings.lead_hunter_auto_dm_enabled, allowed_channels=getattr(settings, 'lead_hunter_allowed_channels', 'telegram'),
        require_personalization=getattr(settings, "lead_hunter_require_personalization", True), block_if_no_official_channel=getattr(settings, "lead_hunter_block_if_no_official_channel", True), confirmed=True,
    )
    await message.answer(("Отправлено." if ok else "Не отправлено автоматически.") + "\n" + result)

@router.message(Command("lead_skip"))
async def lead_skip_cmd(message: Message):
    lead_id = arg_text(message)
    await message.answer("Лид пропущен." if lead_id and mark_skip(lead_id) else "Лид не найден.")

@router.message(Command("lead_report"))
async def lead_report_cmd(message: Message, settings: Settings):
    lead_outreach_enabled = lead_hunter.enabled(
        getattr(settings, "lead_hunter_autopilot_enabled", False)
    )
    niches = {}
    for i in lead_hunter.items:
        niches[i.niche] = niches.get(i.niche, 0) + 1
    await message.answer(
        "Safe Lead Hunter report\n"
        f"leads found/scanned: {lead_hunter.scanned_count}\n"
        f"in queue: {len(lead_hunter.drafts())}\n"
        f"autopilot enabled: {'yes' if lead_outreach_enabled else 'no'}\n"
        f"messages sent: {lead_hunter.sent_today()} / {settings.lead_hunter_daily_dm_limit}\n"
        f"ready_for_manual_send: {lead_hunter.ready_for_manual_send_count()}\n"
        f"sent history: {len(lead_hunter.sent_history)}\n"
        f"blocked by no channel: {lead_hunter.blocked_no_channel}\n"
        f"blocked by safety: {lead_hunter.blocked_safety}\n"
        f"blocked by daily limit: {lead_hunter.blocked_daily_limit}\n"
        f"hot replies: {lead_hunter.hot_replies}\n"
        f"top niches: {', '.join(f'{k}({v})' for k, v in niches.items()) or 'нет'}\n"
        f"last action: {lead_hunter.last_action}\n"
        f"errors: {lead_hunter.last_error or 'нет'}"
    )

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
    active_drafts = post_queue.list_publishable()
    invalid_uniqueness = [p for p in active_drafts if not p.uniqueness_score]
    fallback_count = sum(1 for p in active_drafts if p.fallback_used)
    ollama_count = sum(1 for p in active_drafts if (p.generation_source or p.source) == "ollama")
    avg_viral = round(sum((p.viral_score or metadata_for_text(p.text)['viral_score']) for p in active_drafts) / max(1, len(active_drafts)), 1)
    avg_quality = round(sum((p.quality_score or metadata_for_text(p.text)['quality_score']) for p in active_drafts) / max(1, len(active_drafts)), 1)
    avg_uniqueness = round(sum((p.uniqueness_score or metadata_for_text(p.text)['uniqueness_score']) for p in active_drafts) / max(1, len(active_drafts)), 1)
    critical_uniqueness_line = f"• critical: active drafts have invalid uniqueness score ({len(invalid_uniqueness)})\n" if invalid_uniqueness else ""
    return (
        "📊 AI Growth Marketer — отчёт за день\n\n"
        "🧭 Главный блок:\n"
        f"✅ Overall status: {'работает' if not growth_runtime.last_error else 'нужна проверка'}\n"
        f"✅ Today progress: посты {len(published)}, лиды {lead_hunter.added_count}, комментарии {comment_discovery.posted_today()}\n"
        "➡️ Next action: проверь /next_post и /next_lead\n"
        f"⚠️ Errors: {growth_runtime.last_error or lead_hunter.last_error or 'нет'}\n\n"
        "📝 Контент:\n"
        f"• опубликовано: {len(published)}\n"
        f"• очередь: {post_queue.get_draft_count()} draft\n"
        f"• лучший angle: заявки / Direct / CRM\n"
        f"Опубликовано сегодня: {len(published)}\n"
        f"Посты: {', '.join('#' + p.id for p in published) or 'нет'}\n"
        f"Draft в очереди: {post_queue.get_draft_count()}\n"
        f"Добавлено автопилотом: {growth_runtime.posts_added}\n\n"
        "💬 Комментарии:\n"
        f"• найдено веток: {comment_discovery.found_count}\n"
        f"• опубликовано/подготовлено: {comment_discovery.posted_today()} / {len(comment_discovery.drafts())}\n"
        "• лучший комментарий: короткий полезный инсайт без ссылки и цены\n\n"
        "🔎 Лиды:\n"
        f"• найдено: {lead_hunter.added_count}\n"
        f"• score 80+: {sum(1 for i in lead_hunter.items if i.score >= 80)}\n"
        f"• top niches: {', '.join(sorted({i.niche for i in lead_hunter.items})) or 'нет'}\n"
        f"• ready for manual: {lead_hunter.ready_for_manual_send_count()}\n\n"
        "🔥 Продажи:\n"
        "• входящие: Sales DM Agent\n"
        f"• hot leads: {lead_hunter.hot_replies}\n"
        f"• handoff: {'настроен' if settings.whatsapp_contact_link or settings.whatsapp_phone else 'не настроен'}\n\n"
        "⚠️ Ошибки:\n"
        f"• API: {growth_runtime.last_error or 'нет'}\n"
        "• safety: no spam / no mass DM / manual-first\n"
        f"• limits: duplicate skipped today: {post_queue.get_duplicate_skipped_count_for_date(today)}\n"
        f"last duplicate skipped: {last_duplicate_text}\n\n"
        "🧪 Content Quality:\n"
        f"• drafts in queue: {post_queue.get_draft_count()}\n"
        f"• unique angles: {q['unique_angles']}\n"
        f"• duplicate skipped today: {post_queue.get_duplicate_skipped_count_for_date(today)}\n"
        f"• weak posts rejected today: {post_queue.get_duplicate_skipped_count_for_date(today)}\n"
        f"• avg viral score: {avg_viral}\n"
        f"• avg quality score: {avg_quality}\n"
        f"• avg uniqueness score: {avg_uniqueness}\n"
        f"• ollama count: {ollama_count}\n"
        f"• fallback count: {fallback_count}\n"
        f"• roboticity risk reason: {q['template_risk']} / repeated_angles={q['repeated_angles']} / banal_count={q['banal_count']}\n"
        f"{critical_uniqueness_line}"
        f"• repeated angles: {', '.join(q['repeated_angles']) if q['repeated_angles'] else 'none'}\n"
        f"• recommendation: {'/growth_rebuild' if q['template_risk'] != 'low' else 'keep angle/hook/CTA rotation'}\n\n"
        "🧠 Рекомендация на завтра:\n"
        f"{'Рекомендация: выполнить /growth_rebuild.' if q['template_risk'] == 'high' else 'держать микс форматов, angles и целей'}\n\n"
        "🔧 Технический блок:\n"
        f"Threads API errors: {growth_runtime.last_error or 'нет'}\n"
        f"Ollama: модель {settings.ollama_model}, ollama-first активен; fallback only on Ollama error\n"
        f"Last autopilot action: {growth_runtime.last_action}\n"
        f"Last autopilot error: {growth_runtime.last_error or 'нет'}\n\n"
        "Marketing quality:\n"
        "• позиционирование: AI-боты / заявки / CRM\n"
        f"• посты сегодня ведут к личке: {'yes' if posts_lead_to_dm else 'no'}\n"
        f"• есть риск слабого позиционирования: {'yes' if weak_positioning_risk else 'no'}\n\n"
        "SMM quality:\nSMM Director Report:\n"
        f"• форматов в очереди: {q['formats_count']}\n"
        f"• уникальных angles в очереди: {q['unique_angles']}\n"
        f"• повторяющиеся angles: {', '.join(q['repeated_angles']) if q['repeated_angles'] else 'none'}\n"
        f"• риск роботности: {q['template_risk']}\n"
        f"• рекомендация SMM-директора: {'Рекомендация: выполнить /growth_rebuild.' if q['template_risk'] == 'high' else ('Если очередь однотипная — нажмите /growth_rebuild.' if q['template_risk'] == 'medium' else 'держать микс форматов, angles и целей')}\n\n"
        "Lead Hunter:\n"
        f"leads scanned today: {lead_hunter.scanned_count}\n"
        f"leads added to queue: {lead_hunter.added_count}\n"
        f"outreach drafts ready: {len(lead_hunter.drafts())}\n"
        f"messages sent today: {lead_hunter.sent_today()}\n"
        f"ready for manual send: {lead_hunter.ready_for_manual_send_count()}\n"
        f"last error: {lead_hunter.last_error or 'нет'}\n\n"
        "Safe Comment Discovery:\n"
        f"Найдено веток/источников: {comment_discovery.found_count}\n"
        f"Comment drafts создано: {len(comment_discovery.items)}\n"
        f"Опубликовано: {comment_discovery.posted_today()}\n"
        f"Ждут подтверждения: {len(comment_discovery.drafts())}"
    )

@router.message(Command("growth_report", "today"))
async def growth_report(message: Message, settings: Settings):
    await message.answer(build_growth_report(settings))


@router.message(Command("autopilot_status", "status"))
async def autopilot_status(message: Message, settings: Settings):
    today = datetime.now(timezone.utc).date()
    lead_outreach_enabled = lead_hunter.enabled(
        getattr(settings, "lead_hunter_autopilot_enabled", False)
    )
    await message.answer(
        "⚙️ AI Growth Marketer — автопилот\n\n"
        "🧭 Главный блок:\n"
        f"✅ overall status: {'работает' if growth_runtime.enabled(settings.growth_autopilot_enabled) else 'выключен'}\n"
        f"📊 today progress: постов {post_queue.get_published_count_for_date(today)}, лидов {len(lead_hunter.drafts())}, комментариев {comment_discovery.posted_today()}\n"
        "➡️ next action: /next_post или /next_lead\n"
        f"⚠️ errors: {growth_runtime.last_error or lead_hunter.last_error or 'нет'}\n\n"
        "📌 Модули:\n"
        f"• постинг: {'✅' if settings.threads_auto_posting_enabled else '⚠️'}\n"
        f"• комментарии: {'✅' if settings.comment_discovery_enabled else '⚠️'}\n"
        f"• лиды: {'✅' if settings.lead_hunter_enabled else '⚠️'}\n"
        f"• outreach: {'✅' if lead_outreach_enabled else '⚠️ manual'}\n"
        "• sales: ✅\n"
        f"• daily report: {'✅' if settings.growth_daily_report_enabled else '⚠️'}\n"
        f"• last action: {growth_runtime.last_action}\n"
        f"• last error: {growth_runtime.last_error or 'нет'}\n\n"
        "🔧 Технический блок:\n"
        "Safe Autopilot status\n"
        f"autopilot enabled: {'yes' if growth_runtime.enabled(settings.growth_autopilot_enabled) else 'no'}\n"
        f"growth mode enabled: {'yes' if settings.threads_growth_mode_enabled else 'no'}\n"
        f"viral only: {'yes' if settings.threads_viral_only else 'no'}\n"
        f"model: {settings.ollama_model}\n"
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
        "Lead Hunter:\n"
        f"enabled: {'yes' if settings.lead_hunter_enabled else 'no'}\n"
        f"autopilot enabled: {'yes' if lead_outreach_enabled else 'no'}\n"
        f"auto DM enabled: {'yes' if settings.lead_hunter_auto_dm_enabled else 'no'}\n"
        f"approval required: {'yes' if settings.lead_hunter_approval_required else 'no'}\n"
        f"official channel: {'yes' if any(official_channel_available(i, getattr(settings, 'lead_hunter_allowed_channels', 'telegram')) for i in lead_hunter.drafts()) else 'no'}\n"
        f"daily limit: {settings.lead_hunter_daily_dm_limit}\n"
        f"sent today: {lead_hunter.sent_today()}\n"
        f"queue count: {len(lead_hunter.drafts())}\n\n"
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


@router.message(Command("growth_refill", "refill"))
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



@router.message(Command("growth_rebuild", "rebuild"))
async def growth_rebuild(message: Message, settings: Settings):
    result = rebuild_growth_queue(post_queue, settings.threads_min_queue_size, source="growth-rebuild-command")
    growth_runtime.posts_added += int(result["added"])
    growth_runtime.last_action = f"очередь пересобрана, добавлено {result['added']}"
    await message.answer(
        "Rebuild complete:\n"
        f"removed skipped from queue: {result['removed_skipped']}\n"
        f"removed duplicate angles: {result['removed_duplicate_angles']}\n"
        f"removed old duplicates: {result['removed_old_duplicates']}\n"
        f"removed low uniqueness: {result['removed_low_uniqueness']}\n"
        f"generated attempts: {result['generated_attempts']}\n"
        f"accepted new: {result['accepted']}\n"
        f"queue total: {result['queue_total']}\n"
        f"active unique angles: {result['unique_angles']}\n"
        f"avg viral score: {result['avg_viral_score']}\n"
        f"avg quality score: {result['avg_quality_score']}\n"
        f"avg uniqueness score: {result['avg_uniqueness_score']}\n"
        f"Итоговые formats: {', '.join(result['rubrics'])}\n"
        f"source: {result['source']}\n"
        f"fallback used: {result['fallback_used']}\n"
        f"Итоговые angles: {', '.join(result['angles'])}"
    )

@router.message(Command("growth_plan", "plan"))
async def growth_plan(message: Message):
    today = datetime.now(timezone.utc).date().isoformat()
    await message.answer(
        f"🧠 План на день — {today}\n\n"
        "🎯 Главный маркетинговый фокус дня:\n"
        "Цель дня: набрать доверие и привести людей в личку на аудит заявок.\n\n"
        "📝 Контент:\n"
        "✅ Цель по постам: 3\n"
        "• 10:00 — Expert Insight: почему заявки теряются между Direct и CRM\n"
        "• 14:00 — Case-style: как салон теряет клиентов на записи\n"
        "• 18:00 — Direct CTA: аудит пути заявки\n\n"
        "💬 Комментарии:\n"
        "✅ Цель: 5 полезных комментариев без ссылок и продаж\n\n"
        "🔎 Лиды:\n"
        "✅ Цель: 5 проверенных бизнес-профилей, 1–2 score 80+\n\n"
        "🚫 Что НЕ повторяем:\n"
        "• не используем снова “админ ответил через 2 часа”\n"
        "• не повторяем вчерашний CTA\n"
        "• не пишем про сайты/лендинги\n\n"
        "🔥 Главный оффер дня / CTA дня:\n"
        "“Напишите «аудит» — покажу, где теряются заявки.”\n\n"
        "Что дальше:\n1. Проверь /content\n2. Затем /leads\n3. Вечером открой /today"
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

@router.message(Command("threads_queue", "posts"))
async def threads_queue(message: Message):
    purge_duplicate_drafts(post_queue)
    cleaned = 0
    for draft in list(post_queue.list_publishable()):
        if ensure_active_post_quality(post_queue, draft) is None:
            cleaned += 1
    posts = post_queue.list_publishable()
    if not posts:
        await message.answer("Очередь Threads пустая. Выполните /growth_rebuild.")
        return
    lines = []
    for p in posts:
        meta = metadata_for_text(p.text)
        lines.append(
            f"#{p.id} {p.status}\n"
            f"format: {p.content_format or p.rubric or meta['content_format']}\n"
            f"angle: {p.content_angle or meta['content_angle']}\n"
            f"hook: {(p.hook or meta['hook'])[:90]}\n"
            f"source: {p.generation_source or p.source or 'unknown'}\n"
            f"fallback: {'yes' if p.fallback_used else 'no'}\n"
            f"viral_score: {p.viral_score or meta['viral_score']}\n"
            f"quality_score: {p.quality_score or meta['quality_score']}\n"
            f"uniqueness_score: {p.uniqueness_score or meta['uniqueness_score']}\n"
            f"CTA: {p.cta_type or meta['cta_type']}\n"
            f"preview: {p.text[:120]}"
        )
    warning = "⚠️ Queue cleanup needed. Run /growth_rebuild.\n\n" if cleaned else ""
    await message.answer(warning + "\n\n".join(lines))

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
    quality_result = evaluate_post(post_queue, post.text, meta, exclude_id=post.id)
    if not quality_result.accepted:
        post_queue.mark_duplicate_skipped(post.id, reason=quality_result.reason)
        await message.answer(f"Пост не опубликован: quality check rejected ({quality_result.reason}).")
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

@router.message(Command("threads_next", "next_post"))
async def threads_next(message: Message):
    post = next_unique_publishable_post(post_queue)
    if not post:
        await message.answer("Нет нормальных draft/ready постов. Выполните /growth_rebuild.")
        return
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
