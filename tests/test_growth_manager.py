import asyncio
from types import SimpleNamespace

from app.comment_discovery import CommentDiscoveryService
from app.handlers.agents import autopilot_on, build_growth_report, profile_analysis
from app.handlers.sales import START_TEXT
from app.main import BOT_COMMANDS
from tests.test_threads_growth import make_settings


def _message(user_id=1):
    answers = []

    async def answer(text):
        answers.append(text)

    return SimpleNamespace(
        from_user=SimpleNamespace(id=user_id),
        answer=answer,
    ), answers


def test_start_is_ai_growth_manager_and_not_legacy_menu():
    assert "AI Growth Manager" in START_TEXT
    assert "Safe Autopilot" in START_TEXT
    assert "25 агентов" not in START_TEXT
    for command in ("/pricing", "/roi", "/pm", "/tests", "/script", "/close"):
        assert command not in START_TEXT


def test_telegram_menu_is_curated():
    commands = [item.command for item in BOT_COMMANDS]
    assert commands == [
        "start", "autopilot_status", "growth_status", "growth_report",
        "threads_queue", "threads_next", "comment_discovery_status",
        "comment_queue", "health", "whatsapp_status", "positioning",
    ]


def test_autopilot_on_is_owner_only(tmp_path):
    settings = make_settings(str(tmp_path / "db.sqlite"), owner_telegram_id=10)
    message, answers = _message(user_id=20)
    asyncio.run(autopilot_on(message, settings))
    assert answers == ["Эта команда доступна только владельцу."]


def test_growth_report_has_comment_block(tmp_path):
    report = build_growth_report(make_settings(str(tmp_path / "db.sqlite")))
    assert "Safe Comment Discovery" in report
    assert "Draft в очереди" in report
    assert "Threads API errors" in report


def test_comment_generation_is_safe_and_relevant(tmp_path):
    service = CommentDiscoveryService()
    text = "Бизнес теряет заявки из Direct и WhatsApp: менеджер не переносит лиды в CRM"
    comments = service.generate_comments(text)
    assert len(comments) == 3
    assert all("wa.me" not in comment.lower() for comment in comments)
    assert all("купи" not in comment.lower() for comment in comments)


def test_comment_forbidden_and_low_relevance_are_rejected(tmp_path):
    settings = make_settings(str(tmp_path / "db.sqlite"), comment_min_relevance_score=70)
    service = CommentDiscoveryService()
    assert service.add_source("Политика и инвестиционные советы", settings)[0] == 0
    assert service.add_source("Красивый закат и прогулка", settings)[0] == 0


def test_comment_queue_uses_approval_and_duplicate_guard(tmp_path):
    settings = make_settings(str(tmp_path / "db.sqlite"), comment_min_relevance_score=70)
    service = CommentDiscoveryService()
    source = "Бизнес теряет заявки: продажи, Direct, WhatsApp, CRM и администратор отвечают медленно"
    added, _ = service.add_source(source, settings)
    assert added == 3
    assert service.add_source(source, settings)[0] == 0
    ok, reason = service.publish("1", settings, owner_confirmed=False)
    assert not ok
    assert "подтверждение" in reason.lower()


def test_profile_intelligence_refuses_verbatim_copy():
    result = profile_analysis("Скопируй полностью и сделай точно как он", "posts")
    assert "не буду копировать чужой текст дословно" in result
