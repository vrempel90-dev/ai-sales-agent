"""APScheduler jobs for autonomous publishing."""
import asyncio
import logging
from datetime import datetime
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from app.config import get_settings
from app.content_agent import choose_topic, generate_post, save_generated_post
from app.database import SessionLocal
from app.models import Post
from app.threads_api import ThreadsClient

logger = logging.getLogger(__name__)
scheduler = AsyncIOScheduler()
DEFAULT_TIMES = [(9, 30), (14, 0), (19, 30)]

async def publish_scheduled_post() -> None:
    settings = get_settings()
    if not settings.auto_publish:
        logger.info("AUTO_PUBLISH=false; scheduled publish skipped")
        return
    topic = choose_topic(); text = generate_post(topic)
    db = SessionLocal()
    try:
        post = save_generated_post(text, topic, db)
        result = await ThreadsClient().publish_text_post(text)
        post.status = "published" if result.get("id") or result.get("ok") else "failed"
        post.threads_post_id = str(result.get("id") or result.get("post_id") or "") or None
        post.published_at = datetime.utcnow() if post.status == "published" else None
        db.commit()
    finally:
        db.close()


def schedule_daily_posts() -> None:
    count = min(get_settings().posts_per_day, len(DEFAULT_TIMES))
    for hour, minute in DEFAULT_TIMES[:count]:
        scheduler.add_job(lambda: asyncio.create_task(publish_scheduled_post()), "cron", hour=hour, minute=minute, id=f"post_{hour}_{minute}", replace_existing=True)


def start_scheduler() -> AsyncIOScheduler:
    if not get_settings().auto_publish:
        logger.info("AUTO_PUBLISH=false; scheduler started without publish jobs")
    else:
        schedule_daily_posts()
    if not scheduler.running:
        scheduler.start()
    return scheduler
