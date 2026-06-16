from dataclasses import dataclass
import os
from dotenv import load_dotenv

load_dotenv()


def _bool_env(name: str, default: str = "false") -> bool:
    return os.getenv(name, default).strip().lower() in {"1", "true", "yes", "on"}


def _int_env(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except ValueError:
        return default


def _hours_env(name: str, default: str = "10,14,18") -> list[int]:
    raw = os.getenv(name, default)
    hours: list[int] = []
    for item in raw.split(","):
        item = item.strip()
        if not item:
            continue
        try:
            hour = int(item)
        except ValueError:
            continue
        if 0 <= hour <= 23:
            hours.append(hour)
    return hours or [10, 14, 18]


@dataclass(frozen=True)
class Settings:
    telegram_bot_token: str
    ollama_base_url: str
    ollama_model: str
    database_path: str
    threads_access_token: str
    threads_user_id: str
    threads_api_base_url: str
    threads_auto_publish: bool
    threads_auto_posting_enabled: bool
    threads_auto_posts_per_day: int
    threads_auto_post_hours: list[int]
    threads_auto_post_timezone: str
    threads_auto_generate_if_queue_empty: bool
    threads_daily_post_limit: int

    @property
    def threads_api_configured(self) -> bool:
        return bool(self.threads_access_token and self.threads_user_id)


def get_settings() -> Settings:
    token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    if not token:
        raise RuntimeError("TELEGRAM_BOT_TOKEN не задан. Добавьте токен Telegram-бота в .env или Railway Variables.")

    ollama_base_url = os.getenv("OLLAMA_BASE_URL", "").strip()
    if not ollama_base_url:
        raise RuntimeError("OLLAMA_BASE_URL не задан. Укажите URL отдельного Ollama-сервиса.")

    return Settings(
        telegram_bot_token=token,
        ollama_base_url=ollama_base_url,
        ollama_model=os.getenv("OLLAMA_MODEL", "llama3.2:3b").strip(),
        database_path=os.getenv("DATABASE_PATH", "./ai_sales_agent.db").strip(),
        threads_access_token=os.getenv("THREADS_ACCESS_TOKEN", "").strip(),
        threads_user_id=os.getenv("THREADS_USER_ID", "").strip(),
        threads_api_base_url=os.getenv("THREADS_API_BASE_URL", "https://graph.threads.net").strip(),
        threads_auto_publish=_bool_env("THREADS_AUTO_PUBLISH", "false"),
        threads_auto_posting_enabled=_bool_env("THREADS_AUTO_POSTING_ENABLED", "false"),
        threads_auto_posts_per_day=_int_env("THREADS_AUTO_POSTS_PER_DAY", 3),
        threads_auto_post_hours=_hours_env("THREADS_AUTO_POST_HOURS", "10,14,18"),
        threads_auto_post_timezone=os.getenv("THREADS_AUTO_POST_TIMEZONE", "Asia/Almaty").strip(),
        threads_auto_generate_if_queue_empty=_bool_env("THREADS_AUTO_GENERATE_IF_QUEUE_EMPTY", "true"),
        threads_daily_post_limit=_int_env("THREADS_DAILY_POST_LIMIT", 3),
    )
