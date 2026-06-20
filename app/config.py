"""Application settings for the autonomous Threads AI sales agent."""
from functools import lru_cache
import logging

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

logger = logging.getLogger(__name__)


class Settings(BaseSettings):
    """Environment-driven configuration. Secrets are never logged."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    openai_api_key: str = Field(default="", alias="OPENAI_API_KEY")
    openai_model: str = Field(default="gpt-4o-mini", alias="OPENAI_MODEL")
    threads_access_token: str = Field(default="", alias="THREADS_ACCESS_TOKEN")
    threads_user_id: str = Field(default="", alias="THREADS_USER_ID")
    threads_webhook_verify_token: str = Field(default="", alias="THREADS_WEBHOOK_VERIFY_TOKEN")
    threads_api_base_url: str = Field(default="https://graph.threads.net", alias="THREADS_API_BASE_URL")
    telegram_bot_token: str = Field(default="", alias="TELEGRAM_BOT_TOKEN")
    telegram_chat_id: str = Field(default="", alias="TELEGRAM_CHAT_ID")
    database_url: str = Field(default="sqlite:///./ai_sales_agent.db", alias="DATABASE_URL")
    auto_publish: bool = Field(default=True, alias="AUTO_PUBLISH")
    posts_per_day: int = Field(default=3, alias="POSTS_PER_DAY")
    lead_score_threshold: int = Field(default=70, alias="LEAD_SCORE_THRESHOLD")

    @property
    def database_configured(self) -> bool:
        return bool(self.database_url)

    @property
    def threads_configured(self) -> bool:
        return bool(self.threads_access_token and self.threads_user_id)

    @property
    def telegram_configured(self) -> bool:
        return bool(self.telegram_bot_token and self.telegram_chat_id)

    def log_startup(self) -> None:
        """Log non-sensitive startup configuration."""
        logger.info("OpenAI model: %s", self.openai_model)
        logger.info("auto_publish: %s", self.auto_publish)
        logger.info("posts_per_day: %s", self.posts_per_day)
        logger.info("database configured: %s", self.database_configured)
        logger.info("threads token configured: %s", bool(self.threads_access_token))
        logger.info("telegram configured: %s", self.telegram_configured)
        if not self.threads_configured:
            logger.warning("Threads API credentials are incomplete; Threads actions will be skipped or mocked.")
        if not self.telegram_configured:
            logger.warning("Telegram credentials are incomplete; hot lead notifications will be skipped.")
        if not self.openai_api_key:
            logger.warning("OPENAI_API_KEY is missing; AI functions will return safe fallbacks.")


@lru_cache
def get_settings() -> Settings:
    """Return cached settings instance."""
    return Settings()
