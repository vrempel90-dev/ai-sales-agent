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
