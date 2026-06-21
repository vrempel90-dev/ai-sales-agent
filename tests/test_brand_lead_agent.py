from types import SimpleNamespace

from app.brand_lead_agent import (
    brand_meta_for_text,
    brand_report_block,
    build_brand_profile,
    build_brand_sprint,
    build_brand_today,
    build_hot_reply,
    build_lead_score,
    score_lead,
)
from app.config import Settings
from app.handlers.agents import build_growth_report
from app.post_queue import PostQueue


def settings(**overrides):
    base = dict(
        llm_provider="ollama",
        ollama_base_url="http://ollama:11434",
        ollama_model="qwen2.5:3b",
        openai_api_key="",
        brand_lead_agent_enabled=True,
    )
    base.update(overrides)
    return Settings(**base)


def test_brand_sprint_returns_7_day_plan():
    text = build_brand_sprint(settings())
    assert text.count("День ") == 7
    assert "День 1" in text
    assert "День 7" in text
    assert "CTA:" in text


def test_brand_today_returns_daily_plan_with_cta():
    text = build_brand_today(settings())
    assert "AI Brand Plan Today" in text
    assert "CTA of the day" in text
    assert "Expected inbound keyword: разбор" in text


def test_brand_profile_returns_bio_pinned_cta():
    text = build_brand_profile(settings())
    assert "Bio:" in text
    assert "Закреплённый пост" in text
    assert "CTA:" in text


def test_lead_score_scores_price_question_as_hot_lead():
    data = score_lead("Сколько стоит бот для салона?")
    assert data["score"] >= 80
    answer = build_lead_score("Сколько стоит бот для салона?")
    assert "🔥 Горячий лид" in answer
    assert "should handoff to owner: yes" in answer


def test_lead_score_scores_random_text_as_cold_low_score():
    data = score_lead("классный пост, спасибо")
    assert data["score"] <= 30
    assert "cold" in data["temperature"]


def test_hot_reply_asks_diagnostic_questions():
    reply = build_hot_reply("Мне нужен бот для клиники")
    assert "Куда сейчас приходят заявки" in reply
    assert "кто отвечает первым" in reply
    assert reply.count("?") <= 2


def test_hot_reply_mentions_price_only_when_price_is_asked():
    assert "от 150 000 ₸" in build_hot_reply("Сколько стоит бот для салона?")
    assert "от 150 000 ₸" not in build_hot_reply("Мне нужен бот для салона")


def test_today_and_growth_report_include_brand_lead_agent_block(tmp_path, monkeypatch):
    import app.handlers.agents as agents_handler

    queue = PostQueue(str(tmp_path / "q.db"))
    monkeypatch.setattr(agents_handler, "post_queue", queue)
    report = build_growth_report(settings())
    assert "🧲 Brand & Lead Agent:" in report
    assert "Sprint day:" in report


def test_queue_metadata_includes_brand_day_and_sprint_stage():
    meta = brand_meta_for_text("Напишите разбор — найду 3 точки потери заявок", settings())
    assert "brand_day" in meta
    assert "sprint_stage" in meta
    assert meta["lead_intent"] == "get_dm_with_keyword_razbor"


def test_no_auto_dm_or_live_browser_comments_enabled_by_default():
    s = settings()
    assert s.lead_hunter_auto_dm_enabled is False
    assert s.comment_approval_required is True


def test_new_mode_does_not_require_openai_api_key_and_keeps_ollama_settings():
    s = settings(openai_api_key="")
    assert s.brand_lead_agent_enabled is True
    assert s.openai_api_key == ""
    assert s.llm_provider == "ollama"
    assert s.ollama_base_url == "http://ollama:11434"
    assert s.ollama_model == "qwen2.5:3b"
    assert "AI Brand Plan Today" in build_brand_today(s)
