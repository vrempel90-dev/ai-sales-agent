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


def _float_env(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, str(default)))
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
    ollama_num_ctx: int
    ollama_num_predict: int
    ollama_num_thread: int
    ollama_temperature: float
    ollama_top_p: float
    database_path: str
    public_telegram_bot_link: str
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
    threads_growth_mode_enabled: bool = False
    threads_min_queue_size: int = 7
    threads_viral_only: bool = False
    owner_telegram_id: int | None = None
    lead_auto_reply_enabled: bool = True
    whatsapp_contact_link: str = ""
    whatsapp_phone: str = ""
    growth_autopilot_enabled: bool = False
    growth_daily_report_enabled: bool = False
    growth_report_hour: int = 21
    growth_report_timezone: str = "Asia/Almaty"
    comment_discovery_enabled: bool = True
    comment_auto_reply_enabled: bool = False
    comment_approval_required: bool = True
    comment_daily_limit: int = 3
    comment_search_topics: str = "заявки,продажи,Direct,CRM,администратор,WhatsApp,Telegram,AI-бот"
    comment_min_relevance_score: int = 70
    comment_report_hour: int = 20
    comment_report_timezone: str = "Asia/Almaty"
    lead_hunter_enabled: bool = True
    lead_hunter_autopilot_enabled: bool = False
    lead_hunter_auto_dm_enabled: bool = False
    lead_hunter_approval_required: bool = True
    lead_hunter_daily_dm_limit: int = 3
    lead_hunter_min_score: int = 80
    lead_hunter_allowed_channels: str = "telegram"
    lead_hunter_require_personalization: bool = True
    lead_hunter_block_if_no_official_channel: bool = True
    lead_hunter_report_hour: int = 21
    lead_hunter_timezone: str = "Asia/Almaty"

    autonomous_threads_agent_enabled: bool = False
    autonomous_threads_agent_auto_start: bool = False
    autonomous_threads_agent_dry_run: bool = True
    autonomous_threads_agent_timezone: str = "Asia/Almaty"
    autonomous_threads_daily_post_target: int = 3
    autonomous_threads_daily_comment_limit: int = 5
    autonomous_threads_daily_dm_limit: int = 2
    autonomous_threads_daily_scan_limit: int = 30
    autonomous_threads_min_comment_score: int = 80
    autonomous_threads_min_dm_score: int = 85
    autonomous_threads_start_hour: int = 10
    autonomous_threads_end_hour: int = 20
    autonomous_threads_min_delay_minutes: int = 45
    autonomous_threads_max_delay_minutes: int = 120
    autonomous_threads_comments_enabled: bool = False
    autonomous_threads_dms_enabled: bool = False
    autonomous_threads_browser_mode: bool = False
    autonomous_threads_stop_on_captcha: bool = True
    autonomous_threads_stop_on_checkpoint: bool = True
    autonomous_threads_stop_on_rate_limit: bool = True
    autonomous_threads_stop_on_action_blocked: bool = True
    autonomous_threads_stop_on_login_issue: bool = True
    autonomous_threads_no_mass_dm: bool = True
    autonomous_threads_no_duplicates: bool = True
    autonomous_threads_no_links_in_first_touch: bool = True
    autonomous_threads_no_price_in_first_touch: bool = True
    autonomous_threads_report_enabled: bool = True
    autonomous_threads_report_hour: int = 21
    autonomous_threads_owner_notify: bool = True

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
        ollama_num_ctx=_int_env("OLLAMA_NUM_CTX", 512),
        ollama_num_predict=_int_env("OLLAMA_NUM_PREDICT", 300),
        ollama_num_thread=_int_env("OLLAMA_NUM_THREAD", 1),
        ollama_temperature=_float_env("OLLAMA_TEMPERATURE", 0.7),
        ollama_top_p=_float_env("OLLAMA_TOP_P", 0.9),
        database_path=os.getenv("DATABASE_PATH", "./ai_sales_agent.db").strip(),
        public_telegram_bot_link=os.getenv("PUBLIC_TELEGRAM_BOT_LINK", "").strip(),
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
        threads_growth_mode_enabled=_bool_env("THREADS_GROWTH_MODE_ENABLED", "false"),
        threads_min_queue_size=max(1, _int_env("THREADS_MIN_QUEUE_SIZE", 7)),
        threads_viral_only=_bool_env("THREADS_VIRAL_ONLY", "false"),
        owner_telegram_id=(
            _int_env("OWNER_TELEGRAM_ID", 0)
            if os.getenv("OWNER_TELEGRAM_ID", "").strip()
            else None
        ),
        lead_auto_reply_enabled=_bool_env("LEAD_AUTO_REPLY_ENABLED", "true"),
        whatsapp_contact_link=os.getenv("WHATSAPP_CONTACT_LINK", "").strip(),
        whatsapp_phone=os.getenv("WHATSAPP_PHONE", "").strip(),
        growth_autopilot_enabled=_bool_env("GROWTH_AUTOPILOT_ENABLED", "false"),
        growth_daily_report_enabled=_bool_env("GROWTH_DAILY_REPORT_ENABLED", "false"),
        growth_report_hour=_int_env("GROWTH_REPORT_HOUR", 21),
        growth_report_timezone=os.getenv("GROWTH_REPORT_TIMEZONE", "Asia/Almaty").strip(),
        comment_discovery_enabled=_bool_env("COMMENT_DISCOVERY_ENABLED", "true"),
        comment_auto_reply_enabled=_bool_env("COMMENT_AUTO_REPLY_ENABLED", "false"),
        comment_approval_required=_bool_env("COMMENT_APPROVAL_REQUIRED", "true"),
        comment_daily_limit=max(1, _int_env("COMMENT_DAILY_LIMIT", 3)),
        comment_search_topics=os.getenv(
            "COMMENT_SEARCH_TOPICS",
            "заявки,продажи,Direct,CRM,администратор,WhatsApp,Telegram,AI-бот",
        ).strip(),
        comment_min_relevance_score=_int_env("COMMENT_MIN_RELEVANCE_SCORE", 70),
        comment_report_hour=_int_env("COMMENT_REPORT_HOUR", 20),
        comment_report_timezone=os.getenv("COMMENT_REPORT_TIMEZONE", "Asia/Almaty").strip(),
        lead_hunter_enabled=_bool_env("LEAD_HUNTER_ENABLED", "true"),
        lead_hunter_autopilot_enabled=_bool_env("LEAD_HUNTER_AUTOPILOT_ENABLED", "false"),
        lead_hunter_auto_dm_enabled=_bool_env("LEAD_HUNTER_AUTO_DM_ENABLED", "false"),
        lead_hunter_approval_required=_bool_env("LEAD_HUNTER_APPROVAL_REQUIRED", "true"),
        lead_hunter_daily_dm_limit=max(1, _int_env("LEAD_HUNTER_DAILY_DM_LIMIT", 3)),
        lead_hunter_min_score=_int_env("LEAD_HUNTER_MIN_SCORE", 80),
        lead_hunter_allowed_channels=os.getenv("LEAD_HUNTER_ALLOWED_CHANNELS", "telegram").strip(),
        lead_hunter_require_personalization=_bool_env("LEAD_HUNTER_REQUIRE_PERSONALIZATION", "true"),
        lead_hunter_block_if_no_official_channel=_bool_env("LEAD_HUNTER_BLOCK_IF_NO_OFFICIAL_CHANNEL", "true"),
        lead_hunter_report_hour=_int_env("LEAD_HUNTER_REPORT_HOUR", 21),
        lead_hunter_timezone=os.getenv("LEAD_HUNTER_TIMEZONE", "Asia/Almaty").strip(),
        autonomous_threads_agent_enabled=_bool_env("AUTONOMOUS_THREADS_AGENT_ENABLED", "false"),
        autonomous_threads_agent_auto_start=_bool_env("AUTONOMOUS_THREADS_AGENT_AUTO_START", "false"),
        autonomous_threads_agent_dry_run=_bool_env("AUTONOMOUS_THREADS_AGENT_DRY_RUN", "true"),
        autonomous_threads_agent_timezone=os.getenv("AUTONOMOUS_THREADS_AGENT_TIMEZONE", "Asia/Almaty").strip(),
        autonomous_threads_daily_post_target=_int_env("AUTONOMOUS_THREADS_DAILY_POST_TARGET", 3),
        autonomous_threads_daily_comment_limit=_int_env("AUTONOMOUS_THREADS_DAILY_COMMENT_LIMIT", 5),
        autonomous_threads_daily_dm_limit=_int_env("AUTONOMOUS_THREADS_DAILY_DM_LIMIT", 2),
        autonomous_threads_daily_scan_limit=_int_env("AUTONOMOUS_THREADS_DAILY_SCAN_LIMIT", 30),
        autonomous_threads_min_comment_score=_int_env("AUTONOMOUS_THREADS_MIN_COMMENT_SCORE", 80),
        autonomous_threads_min_dm_score=_int_env("AUTONOMOUS_THREADS_MIN_DM_SCORE", 85),
        autonomous_threads_start_hour=_int_env("AUTONOMOUS_THREADS_START_HOUR", 10),
        autonomous_threads_end_hour=_int_env("AUTONOMOUS_THREADS_END_HOUR", 20),
        autonomous_threads_min_delay_minutes=_int_env("AUTONOMOUS_THREADS_MIN_DELAY_MINUTES", 45),
        autonomous_threads_max_delay_minutes=_int_env("AUTONOMOUS_THREADS_MAX_DELAY_MINUTES", 120),
        autonomous_threads_comments_enabled=_bool_env("AUTONOMOUS_THREADS_COMMENTS_ENABLED", "false"),
        autonomous_threads_dms_enabled=_bool_env("AUTONOMOUS_THREADS_DMS_ENABLED", "false"),
        autonomous_threads_browser_mode=_bool_env("AUTONOMOUS_THREADS_BROWSER_MODE", "false"),
        autonomous_threads_stop_on_captcha=_bool_env("AUTONOMOUS_THREADS_STOP_ON_CAPTCHA", "true"),
        autonomous_threads_stop_on_checkpoint=_bool_env("AUTONOMOUS_THREADS_STOP_ON_CHECKPOINT", "true"),
        autonomous_threads_stop_on_rate_limit=_bool_env("AUTONOMOUS_THREADS_STOP_ON_RATE_LIMIT", "true"),
        autonomous_threads_stop_on_action_blocked=_bool_env("AUTONOMOUS_THREADS_STOP_ON_ACTION_BLOCKED", "true"),
        autonomous_threads_stop_on_login_issue=_bool_env("AUTONOMOUS_THREADS_STOP_ON_LOGIN_ISSUE", "true"),
        autonomous_threads_no_mass_dm=_bool_env("AUTONOMOUS_THREADS_NO_MASS_DM", "true"),
        autonomous_threads_no_duplicates=_bool_env("AUTONOMOUS_THREADS_NO_DUPLICATES", "true"),
        autonomous_threads_no_links_in_first_touch=_bool_env("AUTONOMOUS_THREADS_NO_LINKS_IN_FIRST_TOUCH", "true"),
        autonomous_threads_no_price_in_first_touch=_bool_env("AUTONOMOUS_THREADS_NO_PRICE_IN_FIRST_TOUCH", "true"),
        autonomous_threads_report_enabled=_bool_env("AUTONOMOUS_THREADS_REPORT_ENABLED", "true"),
        autonomous_threads_report_hour=_int_env("AUTONOMOUS_THREADS_REPORT_HOUR", 21),
        autonomous_threads_owner_notify=_bool_env("AUTONOMOUS_THREADS_OWNER_NOTIFY", "true"),
    )
