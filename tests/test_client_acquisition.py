from app.client_acquisition import (
    acquisition_meta_for_text,
    add_daily_acquisition_posts,
    build_audit_offer,
    build_client_reply,
    build_offer_post,
    build_profile_offer,
    client_acquisition_report_block,
)
from app.content_quality import evaluate_post
from app.post_queue import PostQueue
from app.handlers.agents import build_growth_report


class SettingsStub:
    client_acquisition_mode_enabled = True
    client_acquisition_main_keyword = "разбор"
    whatsapp_contact_link = ""
    whatsapp_phone = ""
    growth_autopilot_enabled = False
    threads_growth_mode_enabled = False
    threads_min_queue_size = 7
    threads_viral_only = False
    growth_daily_report_enabled = False
    ollama_model = "qwen2.5:3b"


def test_offer_post_has_razbor_cta_without_price_guarantee_or_links(tmp_path):
    text = build_offer_post()
    lower = text.lower()
    assert "разбор" in lower
    assert "бесплатно" in lower
    assert "150 000" not in text
    assert "₸" not in text
    assert "гарант" not in lower
    assert "http" not in lower


def test_audit_and_profile_offer_blocks():
    audit = build_audit_offer()
    profile = build_profile_offer()
    assert "Био:" in audit
    assert "Закреп:" in audit
    assert "CTA" in audit
    assert "Bio Threads:" in profile
    assert "Закреплённый пост:" in profile
    assert "Короткое описание услуги:" in profile
    assert "разбор" in profile


def test_client_reply_price_and_irrelevant_site():
    price = build_client_reply("Сколько стоит бот?")
    assert "от 150 000 ₸" in price
    assert "диагност" in price.lower() or "разбор" in price.lower()
    site = build_client_reply("А вы сайты делаете?")
    assert site.startswith("Сайты")
    assert "AI-бот" in site or "AI-ботами" in site
    assert "заяв" in site.lower()


def test_client_reply_razbor_starts_diagnostics():
    reply = build_client_reply("Хочу разбор")
    assert "Какая у вас ниша" in reply
    assert "Куда сейчас приходят заявки" in reply
    assert "Есть CRM" in reply


def test_daily_report_contains_client_acquisition_block(tmp_path, monkeypatch):
    import app.handlers.agents as agents_handler

    queue = PostQueue(str(tmp_path / "q.db"))
    monkeypatch.setattr(agents_handler, "post_queue", queue)
    report = build_growth_report(SettingsStub())
    assert "🎯 Client Acquisition:" in report
    assert "mode: enabled" in report
    assert "CTA: “напишите разбор”" in report


def test_queue_metadata_and_offer_quality_and_one_offer_per_day(tmp_path):
    queue = PostQueue(str(tmp_path / "q.db"))
    added_first = add_daily_acquisition_posts(queue)
    added_second = add_daily_acquisition_posts(queue)
    offers = [p for p in queue.list_publishable() if acquisition_meta_for_text(p.text).content_goal == "offer"]
    assert len(offers) <= 1
    assert any(acquisition_meta_for_text(p.text).content_goal == "pain" for p in added_first)
    assert any(acquisition_meta_for_text(p.text).content_goal == "expert" for p in added_first)
    offer = offers[0]
    meta = acquisition_meta_for_text(offer.text)
    assert meta.acquisition_stage == "conversion"
    assert meta.cta_keyword == "разбор"
    assert evaluate_post(queue, offer.text, {"content_angle": "free_audit"}, exclude_id=offer.id).metadata.viral_score >= 75
    assert client_acquisition_report_block(SettingsStub(), queue).count("Offer posts in queue") == 1
