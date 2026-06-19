from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message
from app.autonomous_threads_agent import AutonomousThreadsAgent
from app.config import Settings
from app.handlers.sales import require_owner

router = Router()
_agent_cache: dict[str, AutonomousThreadsAgent] = {}

def get_agent(settings: Settings) -> AutonomousThreadsAgent:
    key = settings.database_path
    agent = _agent_cache.get(key)
    if agent is None:
        agent = AutonomousThreadsAgent(settings)
        _agent_cache[key] = agent
    return agent

def build_agent_status(settings: Settings) -> str:
    agent = get_agent(settings)
    browser_note = "Browser mode is not configured" if settings.autonomous_threads_browser_mode and not agent.browser.configured else "ok"
    return (
        "🤖 Autonomous Threads Growth Agent — status\n\n"
        f"enabled: {agent.runtime_enabled}\n"
        f"auto start: {settings.autonomous_threads_agent_auto_start}\n"
        f"dry run: {agent.dry_run}\n"
        f"browser mode: {settings.autonomous_threads_browser_mode} ({browser_note})\n"
        f"comments enabled: {settings.autonomous_threads_comments_enabled}\n"
        f"DMs enabled: {settings.autonomous_threads_dms_enabled}\n"
        f"daily limits: posts {settings.autonomous_threads_daily_post_target}, comments {settings.autonomous_threads_daily_comment_limit}, DMs {settings.autonomous_threads_daily_dm_limit}, scans {settings.autonomous_threads_daily_scan_limit}\n"
        f"actions today: scans {agent.count_today('scan')}, comments {agent.count_today('comment','sent')}/{agent.count_today('comment','prepared')}, DMs {agent.count_today('dm','sent')}/{agent.count_today('dm','prepared')}\n"
        f"stopped reason: {agent.stopped_reason or 'none'}\n"
        f"last action: {agent.last_action}\n"
        f"last error: {agent.last_error or 'none'}"
    )

@router.message(Command("agent_status"))
async def agent_status(message: Message, settings: Settings):
    await message.answer(build_agent_status(settings))

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
    result = agent.run_once()
    await message.answer(
        "Один цикл выполнен.\n"
        f"score: {result.score}\n"
        f"comment prepared/sent: {result.comment_prepared}/{result.published_comment}\n"
        f"DM prepared/sent: {result.dm_prepared}/{result.sent_dm}\n"
        f"skip reason: {result.skipped_reason or 'none'}\n"
        f"mode: {'dry_run' if agent.dry_run else 'live'}"
    )

@router.message(Command("agent_report"))
async def agent_report(message: Message, settings: Settings):
    await message.answer(get_agent(settings).report())

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
