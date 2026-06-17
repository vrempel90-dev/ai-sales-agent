from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import os
import re
import sqlite3

from app.config import Settings
from app.ollama_client import ask_ollama

HOT_LEAD_PHRASES = (
    "хочу заказать",
    "когда можем созвониться",
    "давайте делать",
    "нужен бот",
    "готов обсудить",
)
AUDIT_AGREE_PHRASES = ("да", "давайте", "согласен", "согласна", "хочу аудит", "мини-аудит", "аудит")
INTEREST_PHRASES = ("интересно", "сколько стоит", "цена", "стоимость", "хочу бота", "расскажите", "можно подробнее")
BUSINESS_MARKERS = (
    "салон", "клиник", "магазин", "ресторан", "кафе", "студ", "школ", "курс", "агентств",
    "недвиж", "услуг", "прода", "заяв", "клиент", "бизнес", "инстаграм", "instagram", "сайт",
)
NEGATIVE_MARKERS = ("дурак", "туп", "хер", "бля", "нах", "fuck", "shit")

_lead_auto_reply_enabled: bool | None = None


@dataclass(frozen=True)
class LeadResponse:
    text: str
    is_hot: bool = False
    summary: str = ""


def init_lead_mode(enabled: bool) -> None:
    global _lead_auto_reply_enabled
    if _lead_auto_reply_enabled is None:
        _lead_auto_reply_enabled = enabled


def is_lead_mode_enabled(settings: Settings | None = None) -> bool:
    if _lead_auto_reply_enabled is not None:
        return _lead_auto_reply_enabled
    return settings.lead_auto_reply_enabled if settings else False


def set_lead_mode(enabled: bool) -> None:
    global _lead_auto_reply_enabled
    _lead_auto_reply_enabled = enabled


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text.strip().lower())


def _has_any(text: str, phrases: tuple[str, ...]) -> bool:
    return any(phrase in text for phrase in phrases)


def _short(text: str, limit: int = 450) -> str:
    text = re.sub(r"\s+", " ", text).strip()
    return text if len(text) <= limit else text[: limit - 1].rstrip() + "…"


def build_lead_prompt(message_text: str) -> str:
    return f"""Ты AI sales-менеджер по AI-чат-ботам и автоматизациям.
Ответь по-русски, коротко, дружелюбно, без агрессивных продаж.
Не называй цену без данных, не обещай прибыль и сроки за 1 день.
Цель: понять бизнес, боль, канал заявок и предложить мини-аудит.
Сообщение клиента: {message_text}
Ответ:"""


def fallback_lead_response(message_text: str) -> LeadResponse:
    normalized = _normalize(message_text)
    is_price = "сколько" in normalized or "цен" in normalized or "стоим" in normalized
    is_hot = _has_any(normalized, HOT_LEAD_PHRASES)

    if is_hot:
        return LeadResponse(
            "Отлично, передам владельцу, чтобы он связался с вами и помог разобрать задачу. "
            "Пока напишите, пожалуйста: какая у вас ниша и где сейчас приходят заявки?",
            True,
            _short(message_text),
        )

    if _has_any(normalized, NEGATIVE_MARKERS):
        return LeadResponse("Понимаю. Давайте без давления: какая задача по заявкам или клиентам у вас сейчас болит сильнее всего?")

    if is_price:
        return LeadResponse(
            "Стоимость зависит от задачи: простой бот для заявок, AI-администратор, CRM-интеграция "
            "или полноценный AI-менеджер продаж. Сначала нужно понять ваш процесс, тогда можно назвать точнее.\n\n"
            "Подскажите, пожалуйста:\n"
            "1. Какая у вас ниша/бизнес?\n"
            "2. Где сейчас приходят заявки: Instagram, Telegram, WhatsApp, сайт?\n"
            "3. Что хотите автоматизировать: ответы, запись, продажи, CRM, напоминания?"
        )

    if _has_any(normalized, AUDIT_AGREE_PHRASES):
        return LeadResponse(
            "Хорошо, для мини-аудита напишите, пожалуйста:\n"
            "1. Нишу бизнеса.\n"
            "2. Ссылку на Instagram/сайт, если есть.\n"
            "3. Куда приходят заявки.\n"
            "4. Сколько заявок в день/неделю.\n"
            "5. Что админ или менеджер делает вручную."
        )

    if _has_any(normalized, INTEREST_PHRASES):
        return LeadResponse(
            "Да, расскажу. Чтобы не предлагать лишнее, уточню 3 вещи:\n"
            "1. Какая у вас ниша/бизнес?\n"
            "2. Где сейчас приходят заявки: Instagram, Telegram, WhatsApp, сайт?\n"
            "3. Что хотите автоматизировать: ответы, запись, продажи, CRM, напоминания?"
        )

    if _has_any(normalized, BUSINESS_MARKERS) or len(normalized.split()) >= 5:
        return LeadResponse(
            f"Понял: { _short(message_text, 120) }\n\n"
            "Часто в такой ситуации боль в том, что заявки теряются, ответы занимают время, нет CRM, "
            "запись ведётся вручную или забывается follow-up. Могу сделать короткий мини-аудит и подсказать, "
            "что лучше автоматизировать первым. Хотите?"
        )

    return LeadResponse(
        "Понял. Я помогаю бизнесу внедрять AI-чат-ботов и автоматизации для заявок, записи, ответов и CRM.\n\n"
        "Подскажите, какая у вас ниша и что сейчас хотите упростить?"
    )


async def generate_lead_response(settings: Settings, message_text: str) -> LeadResponse:
    fallback = fallback_lead_response(message_text)
    if fallback.is_hot:
        return fallback
    try:
        generated = _short(await ask_ollama(settings, build_lead_prompt(message_text)), 900)
    except RuntimeError:
        return fallback
    if not generated or "гарантир" in generated.lower() or "за 1 день" in generated.lower():
        return fallback
    return LeadResponse(generated, fallback.is_hot, fallback.summary)


class LeadConversationStore:
    def __init__(self, database_path: str | None = None):
        self.database_path = database_path or os.getenv("DATABASE_PATH", "./ai_sales_agent.db")
        directory = os.path.dirname(os.path.abspath(self.database_path))
        if directory:
            os.makedirs(directory, exist_ok=True)
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.database_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS lead_conversations (
                    user_id TEXT PRIMARY KEY,
                    username TEXT,
                    full_name TEXT,
                    last_message TEXT NOT NULL,
                    message_count INTEGER NOT NULL DEFAULT 0,
                    updated_at TEXT NOT NULL
                )
                """
            )

    def save_message(self, user_id: int, username: str | None, full_name: str, text: str) -> None:
        now = datetime.now(timezone.utc).isoformat()
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO lead_conversations (user_id, username, full_name, last_message, message_count, updated_at)
                VALUES (?, ?, ?, ?, 1, ?)
                ON CONFLICT(user_id) DO UPDATE SET
                    username = excluded.username,
                    full_name = excluded.full_name,
                    last_message = excluded.last_message,
                    message_count = lead_conversations.message_count + 1,
                    updated_at = excluded.updated_at
                """,
                (str(user_id), username or "", full_name, text, now),
            )


def build_hot_lead_notification(user_id: int, username: str | None, full_name: str, message_text: str, summary: str) -> str:
    username_line = f"@{username}" if username else "без username"
    return (
        "🔥 Горячий лид в Telegram\n"
        f"Имя: {full_name}\n"
        f"Username: {username_line}\n"
        f"User ID: {user_id}\n"
        f"Сообщение: {_short(message_text, 500)}\n"
        f"Summary: {_short(summary or message_text, 500)}"
    )
