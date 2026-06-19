import asyncio
from types import SimpleNamespace
from app.autonomous_threads_agent import AutonomousThreadsAgent, is_safe_comment, is_safe_dm
from app.handlers.autonomous_threads import agent_run_once, build_agent_status, get_agent, _agent_cache
from app.handlers.sales import START_TEXT
from app.prompts.growth_marketer_master_prompt import GROWTH_MARKETER_MASTER_PROMPT
from tests.test_threads_growth import make_settings


def msg(user_id=1):
    answers=[]
    async def answer(text): answers.append(text)
    return SimpleNamespace(from_user=SimpleNamespace(id=user_id), answer=answer, text=""), answers


def test_master_prompt_exists():
    assert "ROLE:" in GROWTH_MARKETER_MASTER_PROMPT
    assert "BUSINESS GOAL:" in GROWTH_MARKETER_MASTER_PROMPT
    assert "no mass DM" in GROWTH_MARKETER_MASTER_PROMPT


def test_defaults_are_safe(tmp_path):
    s = make_settings(str(tmp_path/'db.sqlite'))
    assert s.autonomous_threads_agent_enabled is False
    assert s.autonomous_threads_agent_dry_run is True
    assert s.autonomous_threads_comments_enabled is False
    assert s.autonomous_threads_dms_enabled is False
    assert s.autonomous_threads_browser_mode is False


def test_agent_status_works(tmp_path):
    s = make_settings(str(tmp_path/'db.sqlite'))
    _agent_cache.clear()
    text = build_agent_status(s)
    assert "Autonomous Threads Growth Agent" in text
    assert "dry run: True" in text
    assert "daily limits" in text


def test_run_once_dry_run_sends_nothing(tmp_path):
    s = make_settings(str(tmp_path/'db.sqlite'), owner_telegram_id=1)
    _agent_cache.clear()
    message, answers = msg(1)
    asyncio.run(agent_run_once(message, s))
    assert "comment prepared/sent: True/False" in answers[0]
    assert "DM prepared/sent: True/False" in answers[0]


def test_comment_and_dm_safety_blocks():
    assert not is_safe_comment("Напишите мне https://x.test цена 150 000 ₸")
    assert not is_safe_dm("Срочно купите сегодня https://x.test за 150 000 ₸")


def test_duplicate_profile_blocked(tmp_path):
    s = make_settings(str(tmp_path/'db.sqlite'), autonomous_threads_agent_dry_run=False, autonomous_threads_dms_enabled=True)
    a = AutonomousThreadsAgent(s)
    a.record("dm", profile_id="p1", status="sent")
    assert a.can_dm("p1", 90, True, "Здравствуйте, могу показать короткую схему обработки заявок.")[1] == "duplicate_profile_14d"


def test_daily_limits_work(tmp_path):
    s = make_settings(str(tmp_path/'db.sqlite'), autonomous_threads_agent_dry_run=False, autonomous_threads_comments_enabled=True, autonomous_threads_dms_enabled=True, autonomous_threads_daily_comment_limit=1, autonomous_threads_daily_dm_limit=1)
    a = AutonomousThreadsAgent(s)
    a.record("comment", target_id="t0", status="sent")
    a.record("dm", profile_id="p0", status="sent")
    assert a.can_comment("t1", 90, "Полезный инсайт про скорость ответа и CRM.")[1] == "daily_comment_limit"
    assert a.can_dm("p1", 90, True, "Здравствуйте, могу показать короткую схему обработки заявок.")[1] == "daily_dm_limit"


def test_stop_on_blocking_states(tmp_path):
    class Browser:
        configured = True
        def detect_blocking_state(self): return "captcha"
    s = make_settings(str(tmp_path/'db.sqlite'))
    a = AutonomousThreadsAgent(s, Browser())
    result = a.run_once()
    assert result.skipped_reason == "captcha"
    assert a.stopped_reason == "captcha"


def test_report_includes_required_blocks(tmp_path):
    s = make_settings(str(tmp_path/'db.sqlite'), autonomous_threads_browser_mode=True)
    report = AutonomousThreadsAgent(s).report()
    for part in ["threads scanned", "trash skipped", "comments sent", "DMs sent", "leads found", "captcha/checkpoint/rate limit/action blocked"]:
        assert part in report
    assert "Browser mode is not configured" in report


def test_start_has_autonomous_ux_and_old_commands():
    assert "/agent_status" in START_TEXT
    assert "/agent_report" in START_TEXT
    assert "/today" in START_TEXT
    assert "/system" in START_TEXT
