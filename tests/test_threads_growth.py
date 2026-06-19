import asyncio

from app.agents import VIRAL_THREADS_TEMPLATES
from app.config import Settings
from app.post_queue import PostQueue
from app.threads_growth import (
    MIN_VIRAL_SCORE,
    add_strong_unique_post,
    best_publishable_post,
    ensure_strong_post,
    has_strong_cta,
    is_senior_marketing_post,
    is_truncated_or_fragmented,
    refill_growth_queue,
    score_thread_post,
    validate_growth_post,
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


def test_score_distinguishes_strong_from_weak_post():
    strong = VIRAL_THREADS_TEMPLATES[0]
    weak = "Мы предлагаем уникальный AI-бот и можем показать схему."

    assert score_thread_post(strong) >= MIN_VIRAL_SCORE
    assert score_thread_post(weak) < MIN_VIRAL_SCORE


def test_senior_marketing_post_passes_and_generic_smm_fails():
    assert is_senior_marketing_post(VIRAL_THREADS_TEMPLATES[0])
    assert validate_growth_post(VIRAL_THREADS_TEMPLATES[0])[0]
    generic = (
        "Развивайте бренд с качественным контентом.\n\n"
        "Мы лучшие и используем индивидуальный подход для вашего бизнеса.\n\n"
        "Подписывайтесь, чтобы узнать больше."
    )
    assert not is_senior_marketing_post(generic)
    assert not validate_growth_post(generic)[0]


def test_missing_pain_consequence_or_ai_action_lowers_quality():
    strong = VIRAL_THREADS_TEMPLATES[0]
    no_pain = (
        strong.replace("Ваш админ ответил через 2 часа — клиент уже ушёл.", "Обработка входящих сообщений.")
        .replace("медленный первый ответ", "обычный первый ответ")
        .replace("теряются", "поступают")
    )
    no_consequence = strong.replace("ушёл", "написал").replace("потеря", "ситуация").replace("конкуренту", "вам")
    no_ai_action = strong.replace("отвечает сразу, уточняет запрос и передаёт", "существует рядом с")

    assert score_thread_post(no_pain) < score_thread_post(strong)
    assert score_thread_post(no_consequence) < score_thread_post(strong)
    assert not validate_growth_post(no_ai_action)[0]


def test_weak_cta_and_fragmented_posts_are_rejected():
    weak = VIRAL_THREADS_TEMPLATES[0].rsplit("\n\n", 1)[0] + "\n\nМогу показать схему."

    assert not has_strong_cta(weak)
    assert not validate_growth_post(weak)[0]
    assert is_truncated_or_fragmented("Клиент написал")


def test_whatsapp_link_makes_threads_post_unpublishable():
    post = VIRAL_THREADS_TEMPLATES[0] + "\nhttps://wa.me/70000000000"

    assert not validate_growth_post(post)[0]
    assert score_thread_post(post) < MIN_VIRAL_SCORE


def test_forbidden_web_content_fails_growth_validation():
    post = VIRAL_THREADS_TEMPLATES[0].replace("AI-администратор", "AI-администратор для лендинга")

    assert not validate_growth_post(post)[0]


def test_every_viral_template_has_strong_cta_and_valid_length():
    assert all(has_strong_cta(post) for post in VIRAL_THREADS_TEMPLATES)
    assert all(validate_growth_post(post)[0] for post in VIRAL_THREADS_TEMPLATES)


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


def test_normalized_duplicate_detection_catches_two_hours_variants():
    from app.threads_growth import posts_are_duplicates

    assert posts_are_duplicates(
        "Ваш админ ответил через 2 часа — клиент уже ушёл",
        "Ваш администратор ответил через два часа — клиент ушёл",
    )
    assert posts_are_duplicates(
        "Ваш админ ответил через 2 часа — клиент уже ушёл",
        "Клиент ушёл, пока админ отвечал 2 часа",
    )


def test_duplicate_published_post_is_not_added_again(tmp_path):
    queue = make_queue(tmp_path)
    first = queue.add_post(VIRAL_THREADS_TEMPLATES[0], source="test")
    queue.mark_published(first.id)

    added = add_strong_unique_post(queue, VIRAL_THREADS_TEMPLATES[0], source="test")

    assert added is not None
    assert added.text != first.text
    assert queue.get_draft_count() == 1


def test_duplicate_after_redeploy_state_reload_is_not_publishable(tmp_path):
    db_path = tmp_path / "growth.db"
    queue = PostQueue(str(db_path))
    published = queue.add_post(VIRAL_THREADS_TEMPLATES[0], source="test")
    queue.mark_published(published.id)

    reloaded = PostQueue(str(db_path))
    duplicate = reloaded.add_post(VIRAL_THREADS_TEMPLATES[0], source="after-redeploy")

    from app.threads_growth import next_unique_publishable_post

    assert next_unique_publishable_post(reloaded) is None
    assert reloaded.get_post(duplicate.id).status == "skipped"
    assert reloaded.get_duplicate_skipped_count_for_date(__import__("datetime").date.today()) == 1


def test_growth_refill_does_not_add_draft_similar_to_published_history(tmp_path):
    queue = make_queue(tmp_path)
    published = queue.add_post(VIRAL_THREADS_TEMPLATES[0], source="test")
    queue.mark_published(published.id)

    added = refill_growth_queue(queue, 3)

    assert len(added) == 3
    assert all(post.text != VIRAL_THREADS_TEMPLATES[0] for post in added)


def test_purge_duplicate_drafts_keeps_threads_queue_unique(tmp_path):
    from app.threads_growth import purge_duplicate_drafts

    queue = make_queue(tmp_path)
    keep = queue.add_post(VIRAL_THREADS_TEMPLATES[0], source="test")
    duplicate = queue.add_post(VIRAL_THREADS_TEMPLATES[0], source="test")

    assert purge_duplicate_drafts(queue) == 1
    assert queue.get_post(keep.id).status == "draft"
    assert queue.get_post(duplicate.id).status == "skipped"


def test_autopilot_selects_next_draft_when_first_is_duplicate(tmp_path):
    from app.threads_growth import next_unique_publishable_post

    queue = make_queue(tmp_path)
    published = queue.add_post(VIRAL_THREADS_TEMPLATES[0], source="published")
    queue.mark_published(published.id)
    duplicate = queue.add_post(VIRAL_THREADS_TEMPLATES[0], source="duplicate")
    unique = queue.add_post(VIRAL_THREADS_TEMPLATES[1], source="unique")

    selected = next_unique_publishable_post(queue)

    assert selected.id == unique.id
    assert queue.get_post(duplicate.id).status == "skipped"


def test_anti_banal_guard_rejects_generic_and_accepts_live_expert_post():
    from app.threads_growth import is_not_banal_smm_post

    banal = "AI-бот поможет вашему бизнесу автоматизировать процессы и повышайте эффективность. Напишите нам."
    live = VIRAL_THREADS_TEMPLATES[0]

    assert not is_not_banal_smm_post(banal)
    assert is_not_banal_smm_post(live)


def test_growth_refill_adds_different_formats_angles_and_ctas(tmp_path):
    queue = make_queue(tmp_path)

    added = refill_growth_queue(queue, 7)

    assert len({post.content_format for post in added}) >= 5
    assert len({post.content_angle for post in added}) == len(added)
    assert len({post.cta_type for post in added}) >= 3


def test_growth_rebuild_removes_banal_and_reports_lower_robot_risk(tmp_path):
    from app.threads_growth import rebuild_growth_queue, queue_smm_quality

    queue = make_queue(tmp_path)
    queue.add_post("AI-бот поможет вашему бизнесу автоматизировать процессы. Повышайте эффективность каждый день.", source="bad")
    before = queue_smm_quality(queue)["template_risk"]

    result = rebuild_growth_queue(queue, 5)

    assert before == "high"
    assert result["removed_banal"] >= 1
    assert result["robot_like_risk"] in {"low", "medium"}


def test_content_memory_blocks_first_sentence_format_cta_and_angle(tmp_path):
    from app.threads_growth import content_memory_blocks, metadata_for_text

    queue = make_queue(tmp_path)
    first = add_strong_unique_post(queue, VIRAL_THREADS_TEMPLATES[0], source="test")
    assert first is not None
    meta = metadata_for_text(VIRAL_THREADS_TEMPLATES[0])
    blocked, reason = content_memory_blocks(queue, VIRAL_THREADS_TEMPLATES[0], meta)

    assert blocked
    assert reason in {"first_sentence repeated inside 14 days", "content_angle repeated inside 48h"}
