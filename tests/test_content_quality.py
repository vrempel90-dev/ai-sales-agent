from datetime import datetime, timedelta, timezone

from app.content_quality import evaluate_post
from app.growth_content import VIRAL_THREADS_TEMPLATES
from app.post_queue import PostQueue
from app.threads_growth import add_strong_unique_post, rebuild_growth_queue


def make_queue(tmp_path):
    return PostQueue(str(tmp_path / "content_quality.sqlite"))


def test_content_quality_blocks_semantic_angle_cta_structure_and_weak_posts(tmp_path):
    queue = make_queue(tmp_path)
    accepted = add_strong_unique_post(queue, VIRAL_THREADS_TEMPLATES[0], source="test")
    assert accepted is not None

    assert evaluate_post(queue, VIRAL_THREADS_TEMPLATES[0]).reason == "exact_duplicate"

    same_meaning = VIRAL_THREADS_TEMPLATES[0].replace("Ваш админ", "Администратор").replace("ушёл", "ушел")
    assert evaluate_post(queue, same_meaning).reason in {"exact_duplicate", "semantic_duplicate"}

    duplicate_result = evaluate_post(queue, VIRAL_THREADS_TEMPLATES[0])
    assert duplicate_result.reason in {"exact_duplicate", "semantic_duplicate", "angle_duplicate"}

    regenerated = add_strong_unique_post(queue, VIRAL_THREADS_TEMPLATES[0], source="test")
    assert regenerated is not None
    assert regenerated.content_angle != accepted.content_angle

    generic = "В современном бизнесе AI-боты — это будущее. Автоматизация помогает бизнесу улучшить сервис. Напишите в личку."
    assert evaluate_post(queue, generic).reason in {"robotic_text", "weak_viral_score", "weak_quality_score"}


def test_same_angle_published_last_48h_blocks_and_history_persists(tmp_path):
    db_path = tmp_path / "content_quality.sqlite"
    queue = PostQueue(str(db_path))
    post = queue.add_post(VIRAL_THREADS_TEMPLATES[0], source="test")
    queue.mark_published(post.id)

    reloaded = PostQueue(str(db_path))
    result = evaluate_post(reloaded, VIRAL_THREADS_TEMPLATES[0])
    assert result.reason in {"exact_duplicate", "semantic_duplicate", "angle_duplicate"}
    assert reloaded.list_content_history(days=14)


def test_growth_rebuild_returns_quality_summary_with_unique_angles(tmp_path):
    queue = make_queue(tmp_path)
    queue.add_post("AI-бот поможет вашему бизнесу автоматизировать процессы. Повышайте эффективность каждый день.", source="bad")

    result = rebuild_growth_queue(queue, 7)

    assert result["accepted"] >= 1
    assert result["unique_angles"] >= 1
    assert result["avg_viral_score"] >= 75
    assert result["avg_quality_score"] >= 80


def test_draft_post_cannot_keep_zero_uniqueness_score(tmp_path):
    from app.threads_growth import ensure_active_post_quality

    queue = make_queue(tmp_path)
    post = queue.add_post(VIRAL_THREADS_TEMPLATES[0], source="test")
    with queue._connect() as conn:
        conn.execute("UPDATE threads_posts SET uniqueness_score = 0 WHERE id = ?", (post.id,))

    checked = ensure_active_post_quality(queue, queue.get_post(post.id))

    assert checked is not None
    assert checked.uniqueness_score >= 85


def test_low_uniqueness_rejected_even_with_high_viral_quality(tmp_path):
    queue = make_queue(tmp_path)
    published = queue.add_post(VIRAL_THREADS_TEMPLATES[0], source="history")
    queue.mark_published(published.id)

    result = evaluate_post(queue, VIRAL_THREADS_TEMPLATES[0], {"viral_score": 100, "quality_score": 100})

    assert not result.accepted
    assert result.metadata.uniqueness_score < 85


def test_hook_duplicate_from_duplicate_history_is_rejected(tmp_path):
    queue = make_queue(tmp_path)
    queue.record_duplicate_skip(VIRAL_THREADS_TEMPLATES[0], source="test", reason="skipped duplicate")

    result = evaluate_post(queue, VIRAL_THREADS_TEMPLATES[0].replace("заявку", "лид"))

    assert result.reason in {"exact_duplicate", "semantic_duplicate_history", "hook_duplicate_history", "first_line_duplicate_history"}


def test_rebuild_removes_same_angle_and_keeps_active_unique(tmp_path):
    queue = make_queue(tmp_path)
    first = queue.add_post(VIRAL_THREADS_TEMPLATES[0], source="old")
    dup_angle = queue.add_post(VIRAL_THREADS_TEMPLATES[0].replace("Ваш админ", "Администратор"), source="old")

    result = rebuild_growth_queue(queue, 7)
    active = queue.list_publishable()

    assert queue.get_post(dup_angle.id).status in {"skipped", "rejected_angle_duplicate", "rejected_low_uniqueness"}
    assert result["queue_total"] == 7
    assert result["unique_angles"] == len(active)
    assert result["avg_uniqueness_score"] > 0


def test_skipped_posts_not_publishable_or_next(tmp_path):
    from app.threads_growth import next_unique_publishable_post

    queue = make_queue(tmp_path)
    skipped = queue.add_post(VIRAL_THREADS_TEMPLATES[0], source="test")
    queue.skip_post(skipped.id)
    active = queue.add_post(VIRAL_THREADS_TEMPLATES[1], source="test")

    assert skipped.id not in [p.id for p in queue.list_publishable()]
    assert next_unique_publishable_post(queue).id == active.id
