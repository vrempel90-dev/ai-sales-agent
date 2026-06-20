from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message
from app.autonomous_threads_agent import AutonomousThreadsAgent
from app.threads_browser_layer import ThreadsBrowserLayer
from app.config import Settings
from app.handlers.sales import require_owner
from app.threads_worker_client import ThreadsWorkerQueue

router = Router()
_agent_cache: dict[str, AutonomousThreadsAgent] = {}

def get_agent(settings: Settings) -> AutonomousThreadsAgent:
    key = settings.database_path
    agent = _agent_cache.get(key)
    if agent is None:
        agent = AutonomousThreadsAgent(settings)
        _agent_cache[key] = agent
    return agent

async def _browser_status(settings: Settings):
    layer = ThreadsBrowserLayer(settings)
    try:
        return await layer.check_browser_ready()
    finally:
        await layer.close_browser()

async def build_agent_status(settings: Settings) -> str:
    agent = get_agent(settings)
    bs = await _browser_status(settings)
    browser_note = "ready" if bs.browser_ready else (bs.last_browser_error or ("session not configured" if not bs.session_configured else "browser unavailable"))
    return (
        "🤖 Autonomous Threads Growth Agent — status\n\n"
        f"enabled: {agent.runtime_enabled}\n"
        f"auto start: {settings.autonomous_threads_agent_auto_start}\n"
        f"dry run: {agent.dry_run}\n"
        f"browser execution mode: {settings.threads_browser_execution_mode}\n"
        f"browser mode: {settings.autonomous_threads_browser_mode} ({browser_note})\n"
        f"browser dependencies: {'yes' if bs.playwright_installed else 'no'}\n"
        f"session configured: {'yes' if bs.session_configured else 'no'}\n"
        f"browser ready: {'yes' if bs.browser_ready else 'no'}\n"
        f"live comments ready: {'yes' if bs.live_comments_ready else 'no'}\n"
        f"live DM ready: no\n"
        f"comments enabled: {settings.autonomous_threads_comments_enabled}\n"
        f"DMs enabled: {settings.autonomous_threads_dms_enabled} (Live DM is not implemented yet. DM remains disabled/manual.)\n"
        f"daily limits: posts {settings.autonomous_threads_daily_post_target}, comments {settings.autonomous_threads_daily_comment_limit}, DMs {settings.autonomous_threads_daily_dm_limit}, scans {settings.autonomous_threads_daily_scan_limit}\n"
        f"actions today: scans {agent.count_today('scan')}, comments {agent.count_today('comment','sent')}/{agent.count_today('comment','prepared')}, DMs {agent.count_today('dm','sent')}/{agent.count_today('dm','prepared')}\n"
        f"stopped reason: {agent.stopped_reason or 'none'}\n"
        f"last action: {agent.last_action}\n"
        f"last error: {agent.last_error or 'none'}"
    )

@router.message(Command("agent_status"))
async def agent_status(message: Message, settings: Settings):
    await message.answer(await build_agent_status(settings))

@router.message(Command("agent_on"))
async def agent_on(message: Message, settings: Settings):
    if not await require_owner(message, settings): return
    agent = get_agent(settings); agent.runtime_enabled = True; agent.stopped_reason = ""; agent.last_action = "enabled by owner"
    await message.answer("Autonomous Threads Growth Agent включён в runtime.")

@router.message(Command("agent_off"))
async def agent_off(message: Message, settings: Settings):
    if not await require_owner(message, settings): return
    agent = get_agent(settings); agent.stop_agent("stopped_by_owner")
    await message.answer("Autonomous Threads Growth Agent остановлен.")

@router.message(Command("agent_dry_run_on"))
async def agent_dry_run_on(message: Message, settings: Settings):
    if not await require_owner(message, settings): return
    agent = get_agent(settings); agent.dry_run = True
    await message.answer("dry_run включён: агент анализирует и готовит действия, но ничего не публикует и не отправляет.")

@router.message(Command("agent_dry_run_off"))
async def agent_dry_run_off(message: Message, settings: Settings):
    if not await require_owner(message, settings): return
    agent = get_agent(settings); agent.dry_run = False
    await message.answer("dry_run выключен в runtime. Live-действия всё равно требуют enabled=true, comments/DM flags и настроенный browser layer.")

@router.message(Command("agent_run_once"))
async def agent_run_once(message: Message, settings: Settings):
    if not await require_owner(message, settings): return
    agent = get_agent(settings)
    result = await agent.run_once_async()
    await message.answer(
        "Один цикл выполнен.\n"
        f"score: {result.score}\n"
        f"comment prepared/sent: {result.comment_prepared}/{result.published_comment}\n"
        f"DM prepared/sent: {result.dm_prepared}/{result.sent_dm}\n"
        f"skip reason: {result.skipped_reason or 'none'}\n"
        f"mode: {'dry_run' if agent.dry_run else 'live'}"
    )

@router.message(Command("agent_browser_status"))
async def agent_browser_status(message: Message, settings: Settings):
    bs = await _browser_status(settings)
    await message.answer(
        "🌐 Threads Browser Layer — status\n"
        f"Playwright installed: {'yes' if bs.playwright_installed else 'no'}\n"
        f"browser mode enabled: {'yes' if bs.browser_mode_enabled else 'no'}\n"
        f"session configured: {'yes' if bs.session_configured else 'no'}\n"
        f"can open Threads home: {'yes' if bs.can_open_threads_home else 'no'}\n"
        f"login state: {bs.login_state}\n"
        f"last browser error: {bs.last_browser_error or 'none'}\n"
        f"stopped reason: {bs.stopped_reason or 'none'}"
    )

@router.message(Command("agent_browser_test"))
async def agent_browser_test(message: Message, settings: Settings):
    if not await require_owner(message, settings): return
    layer = ThreadsBrowserLayer(settings)
    bs = await layer.check_browser_ready()
    opened, reason = (False, "browser_unavailable" if bs.session_configured and bs.last_browser_error else "browser not ready")
    if not bs.browser_ready and bs.last_browser_error:
        bs.login_state = "browser_unavailable"
    if bs.browser_ready:
        opened, reason = await layer.open_threads_home()
        bs.can_open_threads_home = opened
        bs.login_state = "ok" if opened else reason
    await layer.close_browser()
    await message.answer(
        "🧪 Safe browser test: no comments, no DMs.\n"
        f"Playwright installed: {'yes' if bs.playwright_installed else 'no'}\n"
        f"session configured: {'yes' if bs.session_configured else 'no'}\n"
        f"can open Threads home: {'yes' if opened else 'no'}\n"
        f"login state: {bs.login_state}\n"
        f"last browser error: {layer.last_browser_error or bs.last_browser_error or 'none'}\n"
        f"reason: {reason}"
    )



def _worker_queue(settings: Settings) -> ThreadsWorkerQueue:
    return ThreadsWorkerQueue(settings.database_path)

@router.message(Command("agent_worker_status"))
async def agent_worker_status(message: Message, settings: Settings):
    summary = _worker_queue(settings).status_summary()
    await message.answer(
        "🖥 Local Threads Browser Worker — status\n"
        f"execution mode: {settings.threads_browser_execution_mode}\n"
        f"worker connected: {'yes' if summary['worker_connected'] else 'no'}\n"
        f"pending tasks: {summary['pending']}\n"
        f"running tasks: {summary['running']}\n"
        f"completed today: {summary['completed_today']}\n"
        f"failed today: {summary['failed_today']}\n"
        f"last worker heartbeat: {summary['last_worker_heartbeat'] or 'none'}\n"
        f"last worker error: {summary['last_worker_error'] or 'none'}\n"
        "DM: disabled/manual only"
    )

@router.message(Command("agent_worker_test"))
async def agent_worker_test(message: Message, settings: Settings):
    if not await require_owner(message, settings): return
    task = _worker_queue(settings).create_task("browser_test")
    await message.answer(
        "🧪 browser_test task queued for local worker.\n"
        f"task_id: {task.task_id}\n"
        "Worker will open Threads home and return opened/login_state/captcha_checkpoint. No comments, no DMs."
    )

@router.message(Command("agent_worker_run_once"))
async def agent_worker_run_once(message: Message, settings: Settings):
    if not await require_owner(message, settings): return
    agent = get_agent(settings)
    task = _worker_queue(settings).create_task("scan_threads", keyword=agent._first_search_keyword())
    agent.record("scan", task.task_id, status="queued", reason="local_worker_run_once", content=task.keyword)
    await message.answer(
        "▶️ One local-worker task queued.\n"
        f"task_id: {task.task_id}\n"
        f"keyword: {task.keyword}\n"
        "Worker will find one relevant thread, score it, prepare a comment, and only publish if comments are enabled and dry_run=false. DM remains manual only."
    )

@router.message(Command("agent_report"))
async def agent_report(message: Message, settings: Settings):
    await message.answer(await get_agent(settings).report_async())

@router.message(Command("agent_plan"))
async def agent_plan(message: Message, settings: Settings):
    await message.answer(
        "🧠 Autonomous Threads Growth Agent — план на день\n\n"
        "• Утро: пост про боль потерянных заявок.\n"
        "• День: поиск Threads по нишам Алматы/Казахстан, чистка мусора, scoring.\n"
        "• Комментарии: до лимита, только score >= min, без ссылок/цен/продажи.\n"
        "• DM: только если личка открыта, score высокий и не было контакта 14 дней.\n"
        "• Вечер: ежедневный отчёт и рекомендация на завтра."
    )

@router.message(Command("agent_history"))
async def agent_history(message: Message, settings: Settings):
    rows = get_agent(settings).history()
    if not rows:
        await message.answer("История Autonomous Threads Growth Agent пуста."); return
    await message.answer("\n".join(f"{r[0]} {r[1]} target={r[2]} profile={r[3]} score={r[4]} status={r[5]} reason={r[6] or '-'}" for r in rows))
