from __future__ import annotations

import asyncio
import os
from dotenv import load_dotenv
from app.local_threads_worker import LocalThreadsBrowserWorker

load_dotenv()


def as_bool(value: str, default: bool = False) -> bool:
    if value == "":
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


async def main():
    database_path = os.getenv("DATABASE_PATH", "./ai_sales_agent.db")
    user_data_dir = os.getenv("LOCAL_THREADS_USER_DATA_DIR", "./threads_chrome_profile")
    headless = as_bool(os.getenv("LOCAL_THREADS_HEADLESS", "false"), False)
    poll_interval = int(os.getenv("LOCAL_THREADS_POLL_INTERVAL_SECONDS", "30"))
    dry_run = as_bool(os.getenv("AUTONOMOUS_THREADS_AGENT_DRY_RUN", "true"), True)
    comments_enabled = as_bool(os.getenv("AUTONOMOUS_THREADS_COMMENTS_ENABLED", "false"), False)
    daily_limit = int(os.getenv("AUTONOMOUS_THREADS_DAILY_COMMENT_LIMIT", "5"))
    worker = LocalThreadsBrowserWorker(database_path, user_data_dir, headless)
    print("Local Threads Browser Worker started")
    print(f"DB: {database_path}")
    print(f"Chrome profile: {user_data_dir}")
    print("If Threads asks for captcha/checkpoint, solve it manually in Chrome. The worker will not bypass protection.")
    try:
        await worker.run_forever(poll_interval, dry_run, comments_enabled, daily_limit)
    finally:
        await worker.close()


if __name__ == "__main__":
    asyncio.run(main())
