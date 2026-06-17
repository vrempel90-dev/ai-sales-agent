from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery
from app.agents import AGENTS, agents_help, build_prompt
from app.config import Settings
from app.keyboards import threads_post_keyboard
from app.ollama_client import ask_ollama, build_ollama_options, test_ollama
from app.post_queue import post_queue, QueuedPost
from app.threads_client import ThreadsClient
from datetime import datetime, timezone

router = Router()
EMPTY_HELP = "Добавьте текст после команды. Пример:\n{example}"
UNKNOWN_COMMAND = "Неизвестная команда. Напишите /agents, чтобы посмотреть список агентов."
OPTIONAL_TEXT_COMMANDS = {"/posts", "/niches"}


def arg_text(message: Message) -> str:
    parts = (message.text or "").split(maxsplit=1)
    return parts[1].strip() if len(parts) > 1 else ""


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
    await message.answer("Готовлю ответ через Ollama...")
    try:
        await message.answer(await ask_ollama(settings, build_prompt(command_name, text)))
    except RuntimeError as e:
        await message.answer(str(e))

@router.message(Command("agents"))
async def cmd_agents(message: Message): await message.answer(agents_help())

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
    return f"Threads draft #{post.id}\nСтатус: {post.status}\n\n{post.text}\n\nПубликация только после подтверждения."

async def show_post(message_or_cb, post: QueuedPost):
    if isinstance(message_or_cb, CallbackQuery):
        await message_or_cb.message.answer(render_post(post), reply_markup=threads_post_keyboard(post.id))
    else:
        await message_or_cb.answer(render_post(post), reply_markup=threads_post_keyboard(post.id))

@router.message(Command("threads_day"))
async def threads_day(message: Message, settings: Settings):
    prompt = "Сгенерируй 5 коротких Threads-постов на сегодня про AI-ботов для бизнеса. Раздели посты строкой --- . В каждом боль бизнеса и мягкий CTA."
    try:
        text = await ask_ollama(settings, prompt)
        posts = [p.strip() for p in text.split("---") if p.strip()][:5]
        if len(posts) < 5: posts = [p.strip() for p in text.split("\n\n") if p.strip()][:5]
        queued = [post_queue.add_post(p) for p in posts]
        await message.answer(f"Добавил в очередь: {len(queued)} постов.")
        if queued: await show_post(message, queued[0])
    except RuntimeError as e: await message.answer(str(e))

@router.message(Command("threads_post"))
async def threads_post(message: Message, settings: Settings):
    topic = arg_text(message)
    if not topic: await message.answer("Добавьте тему после команды. Пример:\n/threads_post AI-бот для салона красоты"); return
    try:
        text = await ask_ollama(settings, f"Сделай один короткий Threads-пост на тему: {topic}. Боль бизнеса, AI-бот, мягкий CTA. Не обещай гарантированную прибыль.")
        await show_post(message, post_queue.add_post(text))
    except RuntimeError as e: await message.answer(str(e))

@router.message(Command("threads_queue"))
async def threads_queue(message: Message):
    posts = post_queue.list_posts()
    if not posts: await message.answer("Очередь Threads пустая."); return
    await message.answer("\n".join(f"#{p.id} — {p.status} — {p.text[:80]}" for p in posts))

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
    post = post_queue.get_next_publishable()
    if not post: await message.answer("Нет постов для публикации."); return
    await publish_by_id(message, settings, post.id)

@router.message(Command("autopost_generate"))
async def autopost_generate(message: Message, settings: Settings):
    await threads_day(message, settings)

async def publish_by_id(message: Message, settings: Settings, pid):
    post = post_queue.get_post(pid)
    if not post: await message.answer("Пост не найден."); return
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
    try:
        new_text = await ask_ollama(settings, f"Переделай Threads-пост: короче, живее, без спама, с мягким CTA.\n\n{post.text}")
        await show_post(message, post_queue.update_post(post.id, new_text))
    except RuntimeError as e: await message.answer(str(e))

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
            try: await show_post(callback, post_queue.update_post(pid, await ask_ollama(settings, f"Переделай Threads-пост короче и живее:\n{post.text}")))
            except RuntimeError as e: await callback.message.answer(str(e))
    elif action == "next":
        post = post_queue.get_next_draft(); await show_post(callback, post) if post else await callback.message.answer("Draft-постов нет.")
    await callback.answer()
