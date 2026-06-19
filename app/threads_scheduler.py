import asyncio
import logging
from datetime import datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from app.config import Settings
from app.post_queue import PostQueue, QueuedPost
from app.threads_growth import (
    add_strong_unique_post,
    next_unique_publishable_post,
    refill_growth_queue,
    validate_growth_post,
    viral_fallback,
)
from app.threads_client import ThreadsClient, THREADS_NOT_CONFIGURED
from app.growth_state import growth_runtime

logger = logging.getLogger(__name__)

SCHEDULER_INTERVAL_SECONDS = 60


def _timezone(name: str) -> ZoneInfo:
    try:
        return ZoneInfo(name)
    except ZoneInfoNotFoundError:
        logger.warning("Unknown THREADS_AUTO_POST_TIMEZONE=%s, falling back to UTC", name)
        return ZoneInfo("UTC")


def _generation_prompt(hour: int) -> str:
    return (
        "Сгенерируй один безопасный короткий Threads-пост для AI Sales Agent. "
        "Тема: AI-боты для бизнеса, продажи, автоматизация ответов клиентам. "
        "До 450 символов, без обещаний гарантированного результата, без спама, "
        "без автолайков, автоподписок, массовых комментариев и автоличек. "
        "Мягкий CTA, только собственный пост. "
        f"Плановый час публикации: {hour}:00."
    )


async def generate_post_if_needed(settings: Settings, queue: PostQueue, scheduled_hour: int) -> QueuedPost | None:
    if not settings.threads_auto_generate_if_queue_empty:
        return None
    # Autogeneration is template-first so publishing remains useful when Ollama is unavailable.
    text = viral_fallback(scheduled_hour)
    is_valid, reason = validate_growth_post(text)
    if not is_valid:
        logger.warning("Generated Threads post failed safety check: %s", reason)
        return None

    post = add_strong_unique_post(
        queue, text, source="auto-generated-viral",
        fallback_index=scheduled_hour, scheduled_hour=scheduled_hour,
    )
    if post is None:
        logger.info("Threads scheduler: no unique viral post available")
        return None
    logger.info("Generated Threads post #%s for scheduled hour %s", post.id, scheduled_hour)
    return post


async def publish_one_scheduled_post(settings: Settings, queue: PostQueue, scheduled_hour: int) -> bool:
    if not settings.threads_auto_publish:
        logger.info("Threads scheduler: THREADS_AUTO_PUBLISH is disabled")
        return False
    post = next_unique_publishable_post(queue)
    if post is None:
        post = await generate_post_if_needed(settings, queue, scheduled_hour)
    if post is None:
        logger.info("Threads scheduler: queue is empty or only duplicates, nothing to publish")
        growth_runtime.last_error = "Автопилот не опубликовал пост: все drafts дублируют published history или не прошли quality check."
        return False

    is_valid, reason = validate_growth_post(post.text)
    if not is_valid:
        queue.mark_failed(post.id, f"safety: {reason}")
        growth_runtime.last_error = f"quality check: {reason}"
        logger.warning("Threads post #%s failed safety check: %s", post.id, reason)
        return False

    if not settings.threads_api_configured:
        logger.error(THREADS_NOT_CONFIGURED)
        return False

    try:
        result = await ThreadsClient(settings).publish_text_post(post.text)
    except Exception:
        logger.exception("Threads scheduler failed to publish post #%s", post.id)
        growth_runtime.last_error = f"Threads API error for post #{post.id}"
        return False

    queue.mark_published(post.id)
    logger.info("Threads scheduler published post #%s. API response: %s", post.id, result)
    growth_runtime.last_action = f"опубликован пост #{post.id}"
    growth_runtime.last_error = ""
    if settings.threads_growth_mode_enabled or growth_runtime.enabled(settings.growth_autopilot_enabled):
        added = refill_growth_queue(queue, settings.threads_min_queue_size, source="growth-after-publish")
        growth_runtime.posts_added += len(added)
    return True


async def run_threads_scheduler(settings: Settings, queue: PostQueue) -> None:
    if not settings.threads_auto_posting_enabled:
        logger.info("Auto Threads Posting: disabled")
        return

    tz = _timezone(settings.threads_auto_post_timezone)
    posted_hours: set[tuple[str, int]] = set()
    autopilot = growth_runtime.enabled(settings.growth_autopilot_enabled)
    if settings.threads_growth_mode_enabled or autopilot:
        added = refill_growth_queue(queue, settings.threads_min_queue_size, source="growth-startup")
        growth_runtime.posts_added += len(added)
        growth_runtime.last_action = f"startup refill: {len(added)}"
    logger.info(
        "Auto Threads Posting: enabled; hours=%s timezone=%s daily_limit=%s",
        settings.threads_auto_post_hours,
        settings.threads_auto_post_timezone,
        settings.threads_daily_post_limit,
    )

    while True:
        try:
            now = datetime.now(tz)
            today_key = now.date().isoformat()
            current_hour = now.hour
            posted_hours = {item for item in posted_hours if item[0] == today_key}
            autopilot = growth_runtime.enabled(settings.growth_autopilot_enabled)
            if (settings.threads_growth_mode_enabled or autopilot) and queue.get_draft_count() < settings.threads_min_queue_size:
                added = refill_growth_queue(queue, settings.threads_min_queue_size)
                growth_runtime.posts_added += len(added)
                growth_runtime.last_action = f"очередь автоматически пополнена на {len(added)}"

            if current_hour in settings.threads_auto_post_hours:
                hour_key = (today_key, current_hour)
                if hour_key in posted_hours:
                    logger.debug("Threads scheduler: hour %s already processed", hour_key)
                else:
                    published_today = queue.get_published_count_for_date(now.date())
                    if published_today >= settings.threads_daily_post_limit:
                        logger.info(
                            "Threads scheduler: daily limit reached (%s/%s)",
                            published_today,
                            settings.threads_daily_post_limit,
                        )
                        posted_hours.add(hour_key)
                    else:
                        await publish_one_scheduled_post(settings, queue, current_hour)
                        posted_hours.add(hour_key)
        except asyncio.CancelledError:
            logger.info("Threads scheduler stopped")
            raise
        except Exception:
            logger.exception("Threads scheduler loop error")

        await asyncio.sleep(SCHEDULER_INTERVAL_SECONDS)
