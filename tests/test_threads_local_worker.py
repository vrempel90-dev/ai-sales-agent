import asyncio

from app.autonomous_threads_agent import AutonomousThreadsAgent
from app.handlers.autonomous_threads import agent_worker_status, agent_worker_test, agent_worker_run_once, _agent_cache
from app.local_threads_worker import LocalThreadsBrowserWorker
from app.threads_worker_client import ThreadsWorkerQueue
from tests.test_threads_growth import make_settings


class Message:
    from_user = type("U", (), {"id": 1})()
    def __init__(self):
        self.answers = []
    async def answer(self, text):
        self.answers.append(text)


def test_execution_mode_disabled_does_not_queue_or_run_browser(tmp_path):
    s = make_settings(str(tmp_path / "db.sqlite"), threads_browser_execution_mode="disabled", autonomous_threads_browser_mode=False)
    result = AutonomousThreadsAgent(s).run_once()
    assert not result.skipped_reason.startswith("queued_local_worker")
    assert ThreadsWorkerQueue(s.database_path).status_summary()["pending"] == 0


def test_execution_mode_local_worker_creates_task_not_railway_browser(tmp_path):
    s = make_settings(str(tmp_path / "db.sqlite"), threads_browser_execution_mode="local_worker", autonomous_threads_browser_mode=True, autonomous_threads_agent_dry_run=False)
    result = asyncio.run(AutonomousThreadsAgent(s).run_once_async())
    summary = ThreadsWorkerQueue(s.database_path).status_summary()
    assert result.skipped_reason.startswith("queued_local_worker")
    assert summary["pending"] == 1


def test_worker_status_shows_pending_tasks(tmp_path):
    s = make_settings(str(tmp_path / "db.sqlite"), owner_telegram_id=1, threads_browser_execution_mode="local_worker")
    ThreadsWorkerQueue(s.database_path).create_task("browser_test")
    msg = Message()
    asyncio.run(agent_worker_status(msg, s))
    assert "execution mode: local_worker" in msg.answers[0]
    assert "pending tasks: 1" in msg.answers[0]


def test_worker_test_creates_browser_test_task(tmp_path):
    s = make_settings(str(tmp_path / "db.sqlite"), owner_telegram_id=1)
    msg = Message()
    asyncio.run(agent_worker_test(msg, s))
    assert "browser_test task queued" in msg.answers[0]
    assert ThreadsWorkerQueue(s.database_path).status_summary()["pending"] == 1


def test_worker_run_once_creates_scan_task(tmp_path):
    s = make_settings(str(tmp_path / "db.sqlite"), owner_telegram_id=1, threads_browser_execution_mode="local_worker")
    _agent_cache.clear()
    msg = Message()
    asyncio.run(agent_worker_run_once(msg, s))
    assert "One local-worker task queued" in msg.answers[0]
    assert ThreadsWorkerQueue(s.database_path).status_summary()["pending"] == 1


def test_local_worker_dry_run_does_not_publish(tmp_path):
    worker = LocalThreadsBrowserWorker(str(tmp_path / "db.sqlite"))
    task = ThreadsWorkerQueue(worker.queue.database_path).create_task("comment_thread", thread_url="https://www.threads.net/@x/post/1", comment_text="safe")
    status, result, error, score = asyncio.run(worker.execute(task, dry_run=True, comments_enabled=True))
    assert status == "done"
    assert result["published"] is False
    assert result["reason"] == "dry_run"


def test_captcha_checkpoint_task_becomes_blocked(monkeypatch, tmp_path):
    worker = LocalThreadsBrowserWorker(str(tmp_path / "db.sqlite"))
    async def fake_browser_test():
        return {"opened": False, "login_state": "captcha", "captcha_checkpoint": True}
    monkeypatch.setattr(worker, "browser_test", fake_browser_test)
    task = worker.queue.create_task("browser_test")
    status, result, error, score = asyncio.run(worker.execute(task))
    assert status == "blocked"
    assert error == "captcha"


def test_dm_remains_disabled_manual(tmp_path):
    worker = LocalThreadsBrowserWorker(str(tmp_path / "db.sqlite"))
    task = worker.queue.create_task("comment_thread", thread_url="https://www.threads.net/@x/post/1", comment_text="safe")
    status, result, error, score = asyncio.run(worker.execute(task, dry_run=True))
    assert result["dm"] == "manual_only"


def test_old_railway_browser_mode_still_safe(tmp_path):
    s = make_settings(str(tmp_path / "db.sqlite"), threads_browser_execution_mode="railway_browser", autonomous_threads_browser_mode=True, autonomous_threads_agent_dry_run=False, autonomous_threads_user_data_dir=str(tmp_path / "missing"))
    result = AutonomousThreadsAgent(s).run_once()
    assert result.skipped_reason == "session not configured"
