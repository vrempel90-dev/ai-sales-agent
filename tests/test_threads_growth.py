import asyncio

from app.agents import VIRAL_THREADS_TEMPLATES, viral_threads_day_posts
from app.config import Settings
from app.post_queue import PostQueue
from app.threads_growth import (
    MIN_VIRAL_SCORE,
    add_strong_unique_post,
    best_publishable_post,
    ensure_strong_post,
    refill_growth_queue,
    score_thread_post,
)
from app.threads_scheduler import generate_post_if_needed


def make_queue(tmp_path) -> PostQueue:
    return PostQueue(str(tmp_path / "growth.db"))


def make_settings(database_path: str, **overrides) -> Settings:
    values = dict(
        telegram_bot_token="token",
        ollama_base_url="http://ollama.test",
        ollama_model="qwen2.5:0.5b",
        ollama_num_ctx=512,
        ollama_num_predict=300,
        ollama_num_thread=1,
        ollama_temperature=0.7,
        ollama_top_p=0.9,
        database_path=database_path,
        public_telegram_bot_link="",
        threads_access_token="",
        threads_user_id="",
        threads_api_base_url="https://graph.threads.net",
        threads_auto_publish=True,
        threads_auto_posting_enabled=True,
        threads_auto_posts_per_day=3,
        threads_auto_post_hours=[10, 14, 18],
        threads_auto_post_timezone="UTC",
        threads_auto_generate_if_queue_empty=True,
        threads_daily_post_limit=3,
        threads_growth_mode_enabled=True,
        threads_min_queue_size=7,
        threads_viral_only=True,
    )
    values.update(overrides)
    return Settings(**values)


def test_growth_refill_fills_queue_to_minimum(tmp_path):
    queue = make_queue(tmp_path)
    queue.add_post(VIRAL_THREADS_TEMPLATES[0], source="existing")

    added = refill_growth_queue(queue, 7)

    assert len(added) == 6
    assert queue.get_draft_count() == 7
    assert len({post.text for post in queue.list_by_status("draft")}) == 7


def test_duplicate_posts_are_not_added(tmp_path):
    queue = make_queue(tmp_path)
    first = add_strong_unique_post(queue, VIRAL_THREADS_TEMPLATES[0], source="test")
    duplicate = add_strong_unique_post(queue, VIRAL_THREADS_TEMPLATES[0], source="test")

    assert first is not None
    assert duplicate is not None
    assert duplicate.text != first.text
    assert queue.get_draft_count() == 2


def test_weak_post_is_replaced_with_viral_fallback():
    result = ensure_strong_post("Мы помогаем бизнесу стать лучше.", fallback_index=1)

    assert result == VIRAL_THREADS_TEMPLATES[1]
    assert score_thread_post(result) >= MIN_VIRAL_SCORE


def test_viral_posts_end_with_strong_cta():
    posts = viral_threads_day_posts()

    assert all("напишите" in post.rsplit("\n\n", 1)[-1].lower() for post in posts)
    assert all(score_thread_post(post) >= MIN_VIRAL_SCORE for post in posts)


def test_weak_cta_is_replaced_by_quality_check():
    weak = (
        "Ваш администратор отвечает медленно, поэтому оплаченная заявка уходит конкуренту.\n\n"
        "AI-бот сразу уточняет запрос, сохраняет контакт и передаёт диалог менеджеру в CRM.\n\n"
        "Если хотите, расскажу."
    )

    result = ensure_strong_post(weak)

    assert "если хотите, расскажу" not in result.lower()
    assert result.endswith("Напишите «аудит» в личку — покажу, где у вас теряются заявки и какой AI-бот это закроет.")


def test_public_telegram_link_is_used_only_by_some_ctas(monkeypatch):
    monkeypatch.setenv("PUBLIC_TELEGRAM_BOT_LINK", "https://t.me/sales_audit_bot")

    posts = viral_threads_day_posts()

    assert any("Напишите «бот» в Telegram: https://t.me/sales_audit_bot" in post for post in posts)
    assert any("в личку" in post for post in posts)
    assert not all("https://t.me/sales_audit_bot" in post for post in posts)


def test_regular_threads_cta_never_contains_whatsapp_link(monkeypatch):
    monkeypatch.setenv("PUBLIC_TELEGRAM_BOT_LINK", "https://t.me/sales_audit_bot")
    monkeypatch.setenv("WHATSAPP_CONTACT_LINK", "https://wa.me/79990000000")

    posts = viral_threads_day_posts()

    assert all("wa.me" not in post.lower() for post in posts)


def test_score_distinguishes_strong_from_weak_post():
    strong = VIRAL_THREADS_TEMPLATES[0]
    weak = "Мы предлагаем уникальный AI-бот и можем показать схему."

    assert score_thread_post(strong) >= MIN_VIRAL_SCORE
    assert score_thread_post(weak) < MIN_VIRAL_SCORE


def test_auto_generate_empty_queue_creates_viral_post(tmp_path):
    queue = make_queue(tmp_path)
    settings = make_settings(queue.database_path)

    post = asyncio.run(generate_post_if_needed(settings, queue, 10))

    assert post is not None
    assert post.source == "auto-generated-viral"
    assert score_thread_post(post.text) >= MIN_VIRAL_SCORE


def test_best_publishable_post_uses_score(tmp_path):
    queue = make_queue(tmp_path)
    queue.add_post("Короткий общий текст про автоматизацию.", source="legacy")
    strong = queue.add_post(VIRAL_THREADS_TEMPLATES[2], source="viral")

    assert best_publishable_post(queue).id == strong.id


def test_irrelevant_website_content_never_survives_generation():
    generated = (
        "Сделаем сайт и лендинг для бизнеса. Веб-приложение увеличит продажи. "
        "Напишите нам, чтобы заказать дизайн сайта."
    )

    result = ensure_strong_post(generated, fallback_index=3)

    lowered = result.lower()
    assert all(word not in lowered for word in ("сайт", "лендинг", "веб-приложение"))
    assert "ai-" in lowered
