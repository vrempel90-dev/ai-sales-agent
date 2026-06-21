import asyncio
from fastapi.testclient import TestClient

from app.config import get_settings


def clear_settings(monkeypatch, token="", auto_publish="false"):
    get_settings.cache_clear()
    monkeypatch.setenv("DATABASE_URL", "sqlite:///:memory:")
    monkeypatch.setenv("DATABASE_PATH", ":memory:")
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", token)
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "123" if token else "")
    monkeypatch.setenv("THREADS_AUTO_PUBLISH", auto_publish)
    monkeypatch.setenv("AUTO_PUBLISH", auto_publish)


def test_lifespan_starts_telegram_polling_task_when_token_exists(monkeypatch):
    clear_settings(monkeypatch, token="token", auto_publish="false")
    events = {"started": asyncio.Event(), "cancelled": False, "scheduler": False}

    async def fake_start_telegram_bot():
        events["started"].set()
        try:
            await asyncio.Future()
        except asyncio.CancelledError:
            events["cancelled"] = True
            raise

    monkeypatch.setattr("app.main.init_db", lambda: None)
    monkeypatch.setattr("app.main.start_scheduler", lambda: events.__setitem__("scheduler", True))
    monkeypatch.setattr("app.main.start_telegram_bot", fake_start_telegram_bot)

    from app.main import app

    with TestClient(app) as client:
        assert client.get("/health").json() == {"status": "ok"}
        assert events["scheduler"] is True
        assert events["started"].is_set()
        assert get_settings().threads_auto_publish is False
    assert events["cancelled"] is True


def test_lifespan_does_not_start_polling_when_token_missing(monkeypatch):
    clear_settings(monkeypatch, token="")
    called = False

    async def fake_start_telegram_bot():
        nonlocal called
        called = True

    monkeypatch.setattr("app.main.init_db", lambda: None)
    monkeypatch.setattr("app.main.start_scheduler", lambda: None)
    monkeypatch.setattr("app.main.start_telegram_bot", fake_start_telegram_bot)

    from app.main import app

    with TestClient(app) as client:
        assert client.get("/health").status_code == 200
    assert called is False


def test_lifespan_polling_startup_does_not_block_fastapi(monkeypatch):
    clear_settings(monkeypatch, token="token")
    started = asyncio.Event()

    async def fake_start_telegram_bot():
        started.set()
        await asyncio.sleep(60)

    monkeypatch.setattr("app.main.init_db", lambda: None)
    monkeypatch.setattr("app.main.start_scheduler", lambda: None)
    monkeypatch.setattr("app.main.start_telegram_bot", fake_start_telegram_bot)

    from app.main import app

    with TestClient(app) as client:
        response = client.get("/health")
        assert response.status_code == 200
        assert started.is_set()


def test_start_telegram_bot_returns_without_token(monkeypatch):
    clear_settings(monkeypatch, token="")

    from app.bot import start_telegram_bot

    asyncio.run(start_telegram_bot())


def test_create_dispatcher_includes_existing_handler_routers(monkeypatch):
    clear_settings(monkeypatch, token="token")
    from app.bot import create_dispatcher
    from app.handlers import agents, autonomous_threads, comments, sales

    dispatcher = create_dispatcher()
    assert dispatcher.routers == [sales.router, agents.router, autonomous_threads.router, comments.router]
    registered = {
        command
        for router in dispatcher.routers
        for filters, _handler in router.message_handlers
        for flt in filters
        for command in getattr(flt, "commands", ())
    }
    expected = {
        "start", "health", "ollama_test", "today", "threads_queue", "threads_next",
        "growth_report", "brand_today", "brand_sprint", "brand_profile", "lead_score",
        "hot_reply", "offer_post", "audit_offer", "profile_offer", "client_reply",
    }
    assert expected <= registered
