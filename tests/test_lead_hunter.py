from types import SimpleNamespace

from app.lead_hunter import (
    add_candidate,
    analyze_candidate,
    lead_hunter,
    lead_hunter_reply_notification,
    message_is_safe,
    next_lead,
    prepare_send,
)
from app.handlers.agents import build_growth_report, render_lead_hunter_status


def settings(**overrides):
    base = dict(
        lead_hunter_enabled=True,
        lead_hunter_autopilot_enabled=False,
        lead_hunter_auto_dm_enabled=False,
        lead_hunter_approval_required=True,
        lead_hunter_daily_dm_limit=3,
        lead_hunter_min_score=70,
        lead_hunter_allowed_channels="telegram",
        lead_hunter_require_personalization=True,
        lead_hunter_block_if_no_official_channel=True,
        comment_discovery_enabled=True,
        comment_approval_required=True,
        threads_growth_mode_enabled=False,
        threads_min_queue_size=7,
        threads_viral_only=False,
        threads_auto_post_hours=[10,14,18],
        threads_auto_publish=False,
        growth_daily_report_enabled=False,
        ollama_model="qwen2.5:3b",
        whatsapp_contact_link="",
        whatsapp_phone="",
    )
    base.update(overrides)
    return SimpleNamespace(**base)


def setup_function():
    lead_hunter.reset()


def salon_text():
    return "Салон красоты, маникюр и косметология. Запись клиентов в Direct и WhatsApp, отзывы, посты, администратор отвечает на заявки."


def test_lead_hunter_status_shows_settings():
    text = render_lead_hunter_status(settings())
    assert "enabled: yes" in text
    assert "auto DM enabled: no" in text
    assert "approval required: yes" in text
    assert "daily DM limit: 3" in text
    assert "min score: 70" in text


def test_lead_scan_suitable_salon_scores_and_queues():
    data, lead, status = add_candidate(salon_text(), 70)
    assert status == "queued"
    assert lead is not None
    assert data["score"] >= 70
    assert len(lead_hunter.drafts()) == 1


def test_personal_profile_not_queued():
    data, lead, status = add_candidate("Личный блог школьника, мысли про политику, без бизнеса и услуг", 70)
    assert lead is None
    assert status == "below_min_score"
    assert data["score"] < 70
    assert not lead_hunter.drafts()


def test_lead_scan_creates_safe_personal_message():
    data = analyze_candidate(salon_text())
    msg = data["draft_message"]
    assert "салон" in msg.lower() or "услуги" in msg.lower()
    assert message_is_safe(msg)[0]
    assert "wa.me" not in msg.lower() and "whatsapp.com" not in msg.lower()
    assert "150 000" not in msg and "₸" not in msg
    assert "купите" not in msg.lower() and "срочно" not in msg.lower() and "гарантирую" not in msg.lower()


def test_queue_and_next_show_draft():
    add_candidate(salon_text(), 70)
    lead = next_lead()
    assert lead is not None
    assert lead.draft_message
    assert lead.score >= 70


def test_lead_send_manual_without_dm_integration_or_approval():
    _, lead, _ = add_candidate(salon_text(), 70)
    ok, result = prepare_send(lead.id, min_score=70, daily_limit=3, approval_required=True, auto_dm_enabled=False)
    assert not ok
    assert "Требуется подтверждение" in result or "ручной отправки" in result
    assert lead.status == "ready_for_manual_send"


def test_daily_limit_blocks_send():
    _, lead, _ = add_candidate(salon_text(), 70)
    lead_hunter.sent_dates.extend([__import__('datetime').date.today().isoformat()] * 3)
    ok, result = prepare_send(lead.id, min_score=70, daily_limit=3, approval_required=False, auto_dm_enabled=True)
    assert not ok
    assert "лимит" in result.lower()


def test_duplicate_lead_or_message_not_added():
    add_candidate(salon_text(), 70)
    _, lead, status = add_candidate(salon_text(), 70)
    assert lead is None
    assert status == "duplicate"
    assert len(lead_hunter.items) == 1


def test_growth_report_contains_lead_hunter_block():
    add_candidate(salon_text(), 70)
    report = build_growth_report(settings())
    assert "Lead Hunter:" in report
    assert "leads scanned today" in report
    assert "outreach drafts ready" in report


def test_autopilot_status_block_text_available():
    status = render_lead_hunter_status(settings())
    assert "Safe Lead Hunter Agent status" in status
    assert "queue-first/manual-send" in status


def test_sales_closing_notification_for_replied_lead():
    note = lead_hunter_reply_notification("салон красоты", "теряет заявки", 86, "Интересно, расскажите")
    assert "Источник: Lead Hunter" in note
    assert "Sales Closing Agent" in note
    assert "WhatsApp" in note


def test_lead_autopilot_run_without_official_channel_ready_manual():
    from app.lead_hunter import run_autopilot_once
    _, lead, _ = add_candidate(salon_text(), 70)
    ok, result = run_autopilot_once(enabled=True, min_score=70, daily_limit=3, auto_dm_enabled=True, approval_required=False, allowed_channels="telegram", require_personalization=True, block_if_no_official_channel=True)
    assert not ok
    assert lead.status == "ready_for_manual_send"
    assert "нет официального канала DM" in result
    assert lead_hunter.sent_today() == 0


def test_safety_guard_blocks_whatsapp_link_and_price_and_duplicate():
    assert not message_is_safe("Здравствуйте, wa.me/777 могу показать схему")[0]
    assert not message_is_safe("Здравствуйте, AI-бот стоит 100000₸, могу показать схему")[0]
    msg = "Здравствуйте. У салон красоты есть заявки. AI-администратор помогает с первым ответом. Могу показать схему."
    assert not message_is_safe(msg, [msg], True)[0]


def test_sent_history_saved_for_official_channel():
    text = salon_text() + " telegram_chat_id:123456"
    _, lead, _ = add_candidate(text, 70)
    ok, result = prepare_send(lead.id, min_score=70, daily_limit=3, approval_required=False, auto_dm_enabled=True, allowed_channels="telegram")
    assert ok
    assert "telegram" in result
    assert lead.status == "sent"
    assert lead_hunter.sent_history[-1].lead_id == lead.id


def _message(user_id=1, text=""):
    answers = []

    async def answer(text):
        answers.append(text)

    return SimpleNamespace(from_user=SimpleNamespace(id=user_id), text=text, answer=answer), answers


def test_lead_autopilot_on_off_owner_only():
    import asyncio
    from app.handlers.agents import lead_autopilot_off, lead_autopilot_on
    cfg = settings(owner_telegram_id=10)
    message, answers = _message(user_id=20)
    asyncio.run(lead_autopilot_on(message, cfg))
    assert answers == ["Эта команда доступна только владельцу."]
    owner_message, owner_answers = _message(user_id=10)
    asyncio.run(lead_autopilot_on(owner_message, cfg))
    assert "LEAD_HUNTER_AUTOPILOT_ENABLED=true" in owner_answers[0]
    asyncio.run(lead_autopilot_off(owner_message, cfg))
    assert "выключен" in owner_answers[-1]


def test_lead_confirm_send_requires_owner():
    import asyncio
    from app.handlers.agents import lead_confirm_send_cmd
    _, lead, _ = add_candidate(salon_text(), 70)
    message, answers = _message(user_id=20, text=f"/lead_confirm_send {lead.id}")
    asyncio.run(lead_confirm_send_cmd(message, settings(owner_telegram_id=10)))
    assert answers == ["Эта команда доступна только владельцу."]


def test_readme_documents_no_scraping_mass_dm_browser_automation():
    text = __import__('pathlib').Path('README.md').read_text()
    assert "нет scraping" in text
    assert "нет browser automation" in text
    assert "нет mass DM" in text
