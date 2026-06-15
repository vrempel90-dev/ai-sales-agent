from dataclasses import dataclass
import os
from dotenv import load_dotenv

load_dotenv()

@dataclass(frozen=True)
class Settings:
    telegram_bot_token: str
    ollama_base_url: str = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    ollama_model: str = os.getenv("OLLAMA_MODEL", "llama3.1:8b")
    threads_access_token: str = os.getenv("THREADS_ACCESS_TOKEN", "")
    threads_user_id: str = os.getenv("THREADS_USER_ID", "")
    threads_api_base_url: str = os.getenv("THREADS_API_BASE_URL", "https://graph.threads.net")
    threads_auto_publish: bool = os.getenv("THREADS_AUTO_PUBLISH", "false").lower() == "true"

def get_settings() -> Settings:
    token = os.getenv("TELEGRAM_BOT_TOKEN", "")
    if not token:
        raise RuntimeError("TELEGRAM_BOT_TOKEN не задан. Добавьте токен Telegram-бота в .env.")
    return Settings(telegram_bot_token=token)
