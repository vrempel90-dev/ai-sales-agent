import asyncio

from app.autonomous_threads_agent import AutonomousThreadsAgent
from app.threads_browser_layer import ThreadsBrowserLayer, duplicate_guard
from app.handlers.autonomous_threads import agent_browser_status, agent_browser_test
from tests.test_threads_growth import make_settings


def test_browser_mode_disabled_does_not_require_playwright(tmp_path):
    s = make_settings(str(tmp_path / "db.sqlite"), autonomous_threads_browser_mode=False)
    status = ThreadsBrowserLayer(s).check_browser_ready()
    assert status.browser_mode_enabled is False
    assert status.browser_ready is False


def test_browser_status_no_session_is_clear(tmp_path):
    s = make_settings(str(tmp_path / "db.sqlite"), autonomous_threads_browser_mode=True, autonomous_threads_user_data_dir=str(tmp_path / "missing"))
    status = ThreadsBrowserLayer(s).check_browser_ready()
    assert status.session_configured is False
    assert status.browser_ready is False


def test_live_run_with_no_session_returns_clear_reason(tmp_path):
    s = make_settings(
        str(tmp_path / "db.sqlite"),
        autonomous_threads_browser_mode=True,
        autonomous_threads_agent_dry_run=False,
        autonomous_threads_comments_enabled=True,
        autonomous_threads_user_data_dir=str(tmp_path / "missing"),
    )
    result = AutonomousThreadsAgent(s).run_once()
    assert result.skipped_reason == "session not configured"


def test_duplicate_browser_history_blocks_thread_profile_and_comment(tmp_path):
    db = str(tmp_path / "db.sqlite")
    assert duplicate_guard(db, "thread", "profile", "Комментарий", "sem") == (True, "ok")
    layer = ThreadsBrowserLayer(make_settings(db))
    layer.save_action_history(db, thread_url="thread", profile_url="profile", comment_text="Комментарий", action_status="sent", sent_at="2099-01-01T00:00:00", semantic_key="sem")
    assert duplicate_guard(db, "thread", "profile2", "Новый", "sem2")[1] == "duplicate_thread"
    assert duplicate_guard(db, "thread2", "profile", "Новый", "sem2")[1] == "duplicate_profile_14d"
    assert duplicate_guard(db, "thread2", "profile2", "Комментарий", "sem2")[1] == "duplicate_comment_text"


def test_agent_browser_commands_do_not_publish(tmp_path):
    class Message:
        from_user = type("U", (), {"id": 1})()
        def __init__(self): self.answers = []
        async def answer(self, text): self.answers.append(text)
    s = make_settings(str(tmp_path / "db.sqlite"), owner_telegram_id=1, autonomous_threads_browser_mode=True, autonomous_threads_user_data_dir=str(tmp_path / "missing"))
    msg = Message()
    asyncio.run(agent_browser_status(msg, s))
    asyncio.run(agent_browser_test(msg, s))
    joined = "\n".join(msg.answers)
    assert "Threads Browser Layer" in joined
    assert "Safe browser test" in joined
    assert AutonomousThreadsAgent(s).count_today("comment", "sent") == 0
