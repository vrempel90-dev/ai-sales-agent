"""Application settings for the autonomous Threads AI sales agent."""
from functools import lru_cache
import logging

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

logger = logging.getLogger(__name__)


class Settings(BaseSettings):
    """Environment-driven configuration. Secrets are never logged."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore", populate_by_name=True)

    llm_provider: str = Field(default="ollama", alias="LLM_PROVIDER")
    ollama_base_url: str = Field(default="http://ollama:11434", alias="OLLAMA_BASE_URL")
    ollama_model: str = Field(default="llama3.2:1b", alias="OLLAMA_MODEL")
    ollama_timeout_seconds: float = Field(default=30.0, alias="OLLAMA_TIMEOUT_SECONDS")
    ollama_num_ctx: int = Field(default=512, alias="OLLAMA_NUM_CTX")
    ollama_num_predict: int = Field(default=256, alias="OLLAMA_NUM_PREDICT")
    ollama_num_thread: int = Field(default=1, alias="OLLAMA_NUM_THREAD")
    ollama_temperature: float = Field(default=0.7, alias="OLLAMA_TEMPERATURE")
    ollama_top_p: float = Field(default=0.9, alias="OLLAMA_TOP_P")
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
    database_path: str = Field(default="./ai_sales_agent.db", alias="DATABASE_PATH")
    owner_telegram_id: int | None = Field(default=None, alias="OWNER_TELEGRAM_ID")
    whatsapp_contact_link: str = Field(default="", alias="WHATSAPP_CONTACT_LINK")
    whatsapp_phone: str = Field(default="", alias="WHATSAPP_PHONE")
    client_acquisition_mode_enabled: bool = Field(default=True, alias="CLIENT_ACQUISITION_MODE_ENABLED")
    client_acquisition_main_keyword: str = Field(default="разбор", alias="CLIENT_ACQUISITION_MAIN_KEYWORD")
    client_acquisition_daily_offer_post_hour: int = Field(default=18, alias="CLIENT_ACQUISITION_DAILY_OFFER_POST_HOUR")
    brand_lead_agent_enabled: bool = Field(default=True, alias="BRAND_LEAD_AGENT_ENABLED")
    brand_lead_agent_positioning: str = Field(default="AI-автоматизатор для бизнесов, которые теряют заявки в Direct / WhatsApp / Telegram", alias="BRAND_LEAD_AGENT_POSITIONING")
    brand_lead_agent_main_offer: str = Field(default="Бесплатно найду 3 места, где ваш бизнес теряет заявки, и покажу, что можно автоматизировать AI-администратором", alias="BRAND_LEAD_AGENT_MAIN_OFFER")
    brand_lead_agent_main_cta: str = Field(default="Напишите “разбор”", alias="BRAND_LEAD_AGENT_MAIN_CTA")
    brand_lead_agent_sprint_days: int = Field(default=7, alias="BRAND_LEAD_AGENT_SPRINT_DAYS")
    brand_lead_agent_daily_posts: int = Field(default=3, alias="BRAND_LEAD_AGENT_DAILY_POSTS")
    brand_lead_agent_target_leads_per_week: int = Field(default=5, alias="BRAND_LEAD_AGENT_TARGET_LEADS_PER_WEEK")
    brand_lead_agent_report_hour: int = Field(default=21, alias="BRAND_LEAD_AGENT_REPORT_HOUR")
    brand_lead_agent_timezone: str = Field(default="Asia/Almaty", alias="BRAND_LEAD_AGENT_TIMEZONE")
    threads_auto_publish: bool = Field(default=True, alias="THREADS_AUTO_PUBLISH")
    threads_auto_posting_enabled: bool = Field(default=True, alias="THREADS_AUTO_POSTING_ENABLED")
    threads_auto_posts_per_day: int = Field(default=3, alias="THREADS_AUTO_POSTS_PER_DAY")
    threads_auto_post_hours: list[int] = Field(default_factory=lambda: [10, 14, 18], alias="THREADS_AUTO_POST_HOURS")
    threads_auto_post_timezone: str = Field(default="UTC", alias="THREADS_AUTO_POST_TIMEZONE")
    threads_auto_generate_if_queue_empty: bool = Field(default=True, alias="THREADS_AUTO_GENERATE_IF_QUEUE_EMPTY")
    threads_daily_post_limit: int = Field(default=3, alias="THREADS_DAILY_POST_LIMIT")
    threads_growth_mode_enabled: bool = Field(default=True, alias="THREADS_GROWTH_MODE_ENABLED")
    threads_min_queue_size: int = Field(default=7, alias="THREADS_MIN_QUEUE_SIZE")
    threads_viral_only: bool = Field(default=False, alias="THREADS_VIRAL_ONLY")
    growth_autopilot_enabled: bool = Field(default=False, alias="GROWTH_AUTOPILOT_ENABLED")
    growth_daily_report_enabled: bool = Field(default=True, alias="GROWTH_DAILY_REPORT_ENABLED")
    comment_discovery_enabled: bool = Field(default=False, alias="COMMENT_DISCOVERY_ENABLED")
    comment_approval_required: bool = Field(default=True, alias="COMMENT_APPROVAL_REQUIRED")
    lead_hunter_enabled: bool = Field(default=True, alias="LEAD_HUNTER_ENABLED")
    lead_hunter_autopilot_enabled: bool = Field(default=False, alias="LEAD_HUNTER_AUTOPILOT_ENABLED")
    lead_hunter_auto_dm_enabled: bool = Field(default=False, alias="LEAD_HUNTER_AUTO_DM_ENABLED")
    lead_hunter_approval_required: bool = Field(default=True, alias="LEAD_HUNTER_APPROVAL_REQUIRED")
    lead_hunter_allowed_channels: str = Field(default="telegram", alias="LEAD_HUNTER_ALLOWED_CHANNELS")
    lead_hunter_daily_dm_limit: int = Field(default=0, alias="LEAD_HUNTER_DAILY_DM_LIMIT")
    lead_hunter_min_score: int = Field(default=70, alias="LEAD_HUNTER_MIN_SCORE")
    lead_hunter_require_personalization: bool = Field(default=True, alias="LEAD_HUNTER_REQUIRE_PERSONALIZATION")
    lead_hunter_block_if_no_official_channel: bool = Field(default=True, alias="LEAD_HUNTER_BLOCK_IF_NO_OFFICIAL_CHANNEL")
    lead_auto_reply_enabled: bool = Field(default=False, alias="LEAD_AUTO_REPLY_ENABLED")
    public_telegram_bot_link: str = Field(default="", alias="PUBLIC_TELEGRAM_BOT_LINK")
    autonomous_threads_agent_enabled: bool = Field(default=False, alias="AUTONOMOUS_THREADS_AGENT_ENABLED")
    autonomous_threads_agent_dry_run: bool = Field(default=True, alias="AUTONOMOUS_THREADS_AGENT_DRY_RUN")
    autonomous_threads_comments_enabled: bool = Field(default=False, alias="AUTONOMOUS_THREADS_COMMENTS_ENABLED")
    autonomous_threads_dms_enabled: bool = Field(default=False, alias="AUTONOMOUS_THREADS_DMS_ENABLED")
    autonomous_threads_daily_comment_limit: int = Field(default=5, alias="AUTONOMOUS_THREADS_DAILY_COMMENT_LIMIT")
    autonomous_threads_daily_dm_limit: int = Field(default=5, alias="AUTONOMOUS_THREADS_DAILY_DM_LIMIT")
    autonomous_threads_browser_mode: bool = Field(default=False, alias="AUTONOMOUS_THREADS_BROWSER_MODE")
    autonomous_threads_user_data_dir: str = Field(default="", alias="AUTONOMOUS_THREADS_USER_DATA_DIR")
    threads_browser_execution_mode: str = Field(default="disabled", alias="THREADS_BROWSER_EXECUTION_MODE")
    comment_min_relevance_score: int = Field(default=70, alias="COMMENT_MIN_RELEVANCE_SCORE")
    comment_auto_reply_enabled: bool = Field(default=False, alias="COMMENT_AUTO_REPLY_ENABLED")
    autonomous_threads_agent_auto_start: bool = Field(default=False, alias="AUTONOMOUS_THREADS_AGENT_AUTO_START")
    autonomous_threads_daily_post_target: int = Field(default=3, alias="AUTONOMOUS_THREADS_DAILY_POST_TARGET")
    autonomous_threads_daily_scan_limit: int = Field(default=10, alias="AUTONOMOUS_THREADS_DAILY_SCAN_LIMIT")
    autonomous_threads_min_dm_score: int = Field(default=80, alias="AUTONOMOUS_THREADS_MIN_DM_SCORE")
    autonomous_threads_min_comment_score: int = Field(default=60, alias="AUTONOMOUS_THREADS_MIN_COMMENT_SCORE")
    autonomous_threads_agent_timezone: str = Field(default="Asia/Almaty", alias="AUTONOMOUS_THREADS_AGENT_TIMEZONE")
    autonomous_threads_start_hour: int = Field(default=9, alias="AUTONOMOUS_THREADS_START_HOUR")
    autonomous_threads_end_hour: int = Field(default=21, alias="AUTONOMOUS_THREADS_END_HOUR")
    autonomous_threads_search_keywords: str = Field(default="салон красоты,клиника,заявки", alias="AUTONOMOUS_THREADS_SEARCH_KEYWORDS")
    autonomous_threads_city: str = Field(default="Алматы", alias="AUTONOMOUS_THREADS_CITY")
    autonomous_threads_browser_headless: bool = Field(default=True, alias="AUTONOMOUS_THREADS_BROWSER_HEADLESS")
    autonomous_threads_cookies_json: str = Field(default="", alias="AUTONOMOUS_THREADS_COOKIES_JSON")
    autonomous_threads_session_file: str = Field(default="", alias="AUTONOMOUS_THREADS_SESSION_FILE")

    @property
    def database_configured(self) -> bool:
        return bool(self.database_url)

    @property
    def threads_api_configured(self) -> bool:
        return self.threads_configured

    @property
    def threads_configured(self) -> bool:
        return bool(self.threads_access_token and self.threads_user_id)

    @property
    def telegram_configured(self) -> bool:
        return bool(self.telegram_bot_token and self.telegram_chat_id)

    def log_startup(self) -> None:
        """Log non-sensitive startup configuration."""
        logger.info("llm_provider: %s", self.llm_provider)
        logger.info("openai configured: %s", bool(self.openai_api_key))
        logger.info("ollama base url configured: %s", bool(self.ollama_base_url))
        logger.info("ollama model: %s", self.ollama_model)
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
        if self.llm_provider.lower() == "openai" and not self.openai_api_key:
            logger.warning("OPENAI_API_KEY is missing; OpenAI AI functions will return safe fallbacks.")
        if self.llm_provider.lower() == "ollama" and not self.ollama_base_url:
            logger.warning("OLLAMA_BASE_URL is missing; Ollama AI functions will return safe fallbacks.")
        if self.llm_provider.lower() not in {"ollama", "openai"}:
            logger.warning("Unknown LLM_PROVIDER=%s; AI functions will return safe fallbacks.", self.llm_provider)


@lru_cache
def get_settings() -> Settings:
    """Return cached settings instance."""
    return Settings()
