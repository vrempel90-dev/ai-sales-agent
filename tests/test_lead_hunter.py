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
        lead_hunter_auto_dm_enabled=False,
        lead_hunter_approval_required=True,
        lead_hunter_daily_dm_limit=3,
        lead_hunter_min_score=70,
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
    assert "Отправьте вручную" in result
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
