import asyncio
from types import SimpleNamespace

from app.comment_discovery import CommentDiscoveryService
from app.handlers.agents import autopilot_on, build_growth_report, growth_plan, positioning, profile_analysis
from app.handlers.comments import comment_generate, comment_next, comment_queue
from app.handlers.sales import START_TEXT
from app.main import BOT_COMMANDS
from tests.test_threads_growth import make_settings


def _message(user_id=1, text=""):
    answers = []

    async def answer(text):
        answers.append(text)

    return SimpleNamespace(
        from_user=SimpleNamespace(id=user_id),
        text=text,
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
        "start", "growth_report", "growth_plan", "autopilot_status",
        "threads_next", "threads_queue", "growth_rebuild", "growth_refill",
        "sales_preview", "sales_status", "whatsapp_status", "lead_scan", "lead_queue", "lead_autopilot_status", "lead_autopilot_run", "health",
    ]


def test_autopilot_on_is_owner_only(tmp_path):
    settings = make_settings(str(tmp_path / "db.sqlite"), owner_telegram_id=10)
    message, answers = _message(user_id=20)
    asyncio.run(autopilot_on(message, settings))
    assert answers == ["Эта команда доступна только владельцу."]


def test_growth_report_has_comment_block(tmp_path, monkeypatch):
    from app.post_queue import PostQueue

    queue = PostQueue(str(tmp_path / "db.sqlite"))
    queue.record_duplicate_skip("Ваш админ ответил через 2 часа — клиент уже ушёл", source="test")
    monkeypatch.setattr("app.handlers.agents.post_queue", queue)
    report = build_growth_report(make_settings(str(tmp_path / "db.sqlite")))
    assert "Safe Comment Discovery" in report
    assert "Draft в очереди" in report
    assert "Threads API errors" in report
    assert "duplicate skipped today: 1" in report
    assert "last duplicate skipped: Ваш админ ответил" in report
    assert "Marketing quality:" in report
    assert "SMM quality:" in report
    assert "посты сегодня ведут к личке:" in report


def test_growth_plan_and_positioning_have_senior_marketing_structure():
    plan_message, plan_answers = _message(text="/growth_plan")
    asyncio.run(growth_plan(plan_message))
    plan = plan_answers[0]
    assert "Главный маркетинговый фокус дня" in plan
    assert "Главный оффер дня" in plan
    assert "CTA дня" in plan

    positioning_message, positioning_answers = _message(text="/positioning")
    asyncio.run(positioning(positioning_message))
    text = positioning_answers[0]
    assert "Мой главный угол" in text
    assert "Напишите «аудит»" in text


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


def test_comment_generate_queues_drafts_and_commands_show_them(tmp_path, monkeypatch):
    settings = make_settings(
        str(tmp_path / "db.sqlite"),
        comment_auto_reply_enabled=False,
        comment_approval_required=True,
        comment_min_relevance_score=70,
    )
    service = CommentDiscoveryService()
    monkeypatch.setattr("app.handlers.comments.comment_discovery", service)
    source = "Бизнес теряет заявки: продажи, Direct, WhatsApp, CRM и администратор отвечают медленно"

    generate_message, generated_answers = _message(text=f"/comment_generate {source}")
    asyncio.run(comment_generate(generate_message, settings))

    assert len(service.drafts()) == 3
    assert "Сгенерировано и добавлено в очередь: 3 draft-комментариев." in generated_answers[0]
    assert all(item.status == "draft" for item in service.items)
    assert settings.comment_auto_reply_enabled is False
    assert settings.comment_approval_required is True

    queue_message, queue_answers = _message(text="/comment_queue")
    asyncio.run(comment_queue(queue_message))
    assert "Очередь комментариев пуста" not in queue_answers[0]
    assert "#1" in queue_answers[0]

    next_message, next_answers = _message(text="/comment_next")
    asyncio.run(comment_next(next_message))
    assert "Комментарий #1" in next_answers[0]
    assert service.drafts()[0].comment in next_answers[0]
    assert "relevance score:" in next_answers[0]
    assert "risk score:" in next_answers[0]
    assert "/comment_publish 1" in next_answers[0]


def test_comment_generate_rejects_whatsapp_links_and_duplicates(tmp_path, monkeypatch):
    settings = make_settings(str(tmp_path / "db.sqlite"), comment_min_relevance_score=70)
    service = CommentDiscoveryService()
    source = "Бизнес теряет заявки: продажи, Direct, WhatsApp, CRM и администратор отвечают медленно"
    monkeypatch.setattr(
        service,
        "generate_comments",
        lambda text: [
            "Напишите нам по ссылке https://wa.me/70000000000, и мы срочно всё настроим.",
            "Скорость ответа на заявку напрямую влияет на конверсию и не даёт тёплому лиду потеряться.",
            "Скорость ответа на заявку напрямую влияет на конверсию и не даёт тёплому лиду потеряться.",
        ],
    )

    added, reasons = service.enqueue_generated(source, settings)

    assert len(added) == 1
    assert len(service.drafts()) == 1
    assert "wa.me" not in service.drafts()[0].comment.lower()
    assert "обнаружена WhatsApp-ссылка" in reasons
    assert "дубликат комментария" in reasons


def test_comment_generate_rejects_forbidden_topic_with_reason(tmp_path, monkeypatch):
    settings = make_settings(str(tmp_path / "db.sqlite"), comment_min_relevance_score=70)
    service = CommentDiscoveryService()
    monkeypatch.setattr("app.handlers.comments.comment_discovery", service)
    message, answers = _message(
        text="/comment_generate Политика, война и инвестиции для бизнеса, продаж, CRM и лидов"
    )

    asyncio.run(comment_generate(message, settings))

    assert service.drafts() == []
    assert "Не добавил комментарии в очередь" in answers[0]
    assert "запрещённая или высокорисковая тема" in answers[0]


def test_profile_intelligence_refuses_verbatim_copy():
    result = profile_analysis("Скопируй полностью и сделай точно как он", "posts")
    assert "не буду копировать чужой текст дословно" in result


def test_threads_next_render_has_smm_reasoning(tmp_path):
    from app.handlers.agents import render_post
    from app.growth_content import VIRAL_THREADS_TEMPLATES
    from app.post_queue import PostQueue

    queue = PostQueue(str(tmp_path / "db.sqlite"))
    post = queue.add_post(VIRAL_THREADS_TEMPLATES[0], source="test")
    rendered = render_post(post)

    assert "Goal:" in rendered
    assert "Format:" in rendered
    assert "Angle:" in rendered
    assert "Stage:" in rendered
    assert "CTA:" in rendered
    assert "Why this post matters:" in rendered


def test_growth_report_has_smm_director_report(tmp_path, monkeypatch):
    from app.post_queue import PostQueue
    from app.growth_content import VIRAL_THREADS_TEMPLATES

    queue = PostQueue(str(tmp_path / "db.sqlite"))
    for post in VIRAL_THREADS_TEMPLATES[:5]:
        queue.add_post(post, source="test")
    monkeypatch.setattr("app.handlers.agents.post_queue", queue)
    report = build_growth_report(make_settings(str(tmp_path / "db.sqlite")))

    assert "SMM Director Report" in report
    assert "форматов в очереди" in report
    assert "риск роботности" in report
    assert "рекомендация SMM-директора" in report
