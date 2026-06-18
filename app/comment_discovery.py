from dataclasses import dataclass
from datetime import datetime, timezone
from difflib import SequenceMatcher
import re

from app.config import Settings

FORBIDDEN_TOPICS = (
    "политик", "религи", "трагеди", "диагноз", "лечени", "инвестиц",
    "несовершеннолет", "nsfw", "конфликт", "войн",
)
RELEVANT_TOPICS = (
    "заяв", "продаж", "direct", "telegram", "whatsapp", "crm", "администратор",
    "менеджер", "лид", "автоматизац", "ai-бот", "ai бот", "чат-бот", "запис",
    "салон", "клиник", "онлайн-школ", "бизнес",
)
AGGRESSIVE = ("купи", "срочно напиши", "пиши в whatsapp", "я сделаю тебе", "wa.me/")


@dataclass
class CommentDraft:
    id: str
    source: str
    summary: str
    relevance_score: int
    risk_score: int
    comment: str
    rationale: str
    status: str = "draft"
    created_at: str = ""


class CommentDiscoveryService:
    """Safe queue-first discovery. It never scrapes Threads or mass-posts."""

    def __init__(self):
        self.items: list[CommentDraft] = []
        self.last_action = "ещё не запускался"
        self.last_error = ""
        self.found_count = 0

    @staticmethod
    def score_source(text: str) -> tuple[int, int]:
        normalized = (text or "").lower()
        relevance = min(100, sum(term in normalized for term in RELEVANT_TOPICS) * 18)
        risk = min(100, sum(term in normalized for term in FORBIDDEN_TOPICS) * 45)
        return relevance, risk

    @staticmethod
    def generate_comments(text: str) -> list[str]:
        relevance, risk = CommentDiscoveryService.score_source(text)
        if risk or relevance < 18:
            return []
        return [
            "Часто проблема не в количестве заявок, а в скорости первого ответа. Пока клиент ждёт, он уже пишет конкуренту.",
            "У многих бизнесов заявки теряются между Direct, Telegram, WhatsApp и CRM. Именно этот участок обычно никто не считает.",
            "AI-бот здесь полезен как первый фильтр: быстро принять заявку, уточнить запрос и не дать контакту потеряться.",
        ]

    @staticmethod
    def quality_passes(comment: str) -> bool:
        return CommentDiscoveryService.comment_quality_reason(comment) == "ok"

    @staticmethod
    def comment_quality_reason(comment: str) -> str:
        lowered = (comment or "").lower()
        if not 40 <= len(comment) <= 300:
            return "недопустимая длина комментария"
        if "wa.me/" in lowered or "whatsapp.com/" in lowered:
            return "обнаружена WhatsApp-ссылка"
        if "http://" in lowered or "https://" in lowered:
            return "обнаружена ссылка"
        if any(marker in lowered for marker in AGGRESSIVE):
            return "обнаружена агрессивная продажа"
        return "ok"

    def _duplicate(self, comment: str) -> bool:
        normalized = re.sub(r"\W+", " ", comment.lower()).strip()[:180]
        return any(
            SequenceMatcher(
                None, normalized, re.sub(r"\W+", " ", item.comment.lower()).strip()[:180]
            ).ratio() >= 0.86
            for item in self.items
        )

    def add_source(self, text: str, settings: Settings) -> tuple[int, str]:
        added, reasons = self.enqueue_generated(text, settings)
        return len(added), "ok" if added else "; ".join(reasons)

    def enqueue_generated(
        self, text: str, settings: Settings
    ) -> tuple[list[CommentDraft], list[str]]:
        self.found_count += 1
        relevance, risk = self.score_source(text)
        if any(term in text.lower() for term in FORBIDDEN_TOPICS):
            return [], ["запрещённая или высокорисковая тема"]
        if relevance < settings.comment_min_relevance_score:
            return [], [f"relevance {relevance} ниже порога {settings.comment_min_relevance_score}"]
        if risk > 20:
            return [], [f"risk {risk} выше допустимого значения 20"]
        comments = self.generate_comments(text)
        added: list[CommentDraft] = []
        reasons: list[str] = []
        for comment in comments:
            quality_reason = self.comment_quality_reason(comment)
            if quality_reason != "ok":
                reasons.append(quality_reason)
                continue
            if self._duplicate(comment):
                reasons.append("дубликат комментария")
                continue
            item = CommentDraft(
                id=str(len(self.items) + 1),
                source=text[:500],
                summary=text[:120],
                relevance_score=relevance,
                risk_score=risk,
                comment=comment,
                rationale="Тема связана с обработкой заявок; комментарий полезный и без прямой продажи.",
                created_at=datetime.now(timezone.utc).isoformat(),
            )
            self.items.append(item)
            added.append(item)
        if not comments:
            reasons.append("не удалось создать комментарии по теме")
        self.last_action = f"обработан источник, добавлено draft: {len(added)}"
        self.last_error = "" if added else "; ".join(reasons)
        return added, reasons or ["нет новых уникальных комментариев"]

    def drafts(self) -> list[CommentDraft]:
        return [item for item in self.items if item.status == "draft"]

    def posted_today(self) -> int:
        today = datetime.now(timezone.utc).date().isoformat()
        return sum(item.status == "published" and item.created_at.startswith(today) for item in self.items)

    def publish(self, item_id: str, settings: Settings, owner_confirmed: bool) -> tuple[bool, str]:
        item = next((candidate for candidate in self.items if candidate.id == str(item_id)), None)
        if not item or item.status != "draft":
            return False, "Комментарий не найден."
        if settings.comment_approval_required and not owner_confirmed:
            return False, "Требуется подтверждение владельца."
        if self.posted_today() >= settings.comment_daily_limit:
            return False, "Дневной лимит комментариев исчерпан."
        if item.relevance_score < settings.comment_min_relevance_score or item.risk_score > 20:
            return False, "Комментарий не прошёл relevance/risk guard."
        if not self.quality_passes(item.comment):
            return False, "Комментарий не прошёл quality guard."
        # There is no official search/reply integration in this project. Approval marks
        # the draft ready for manual publication instead of pretending it was posted.
        item.status = "approved"
        self.last_action = f"комментарий #{item.id} подтверждён для ручной публикации"
        return True, "Комментарий подтверждён. Опубликуйте его вручную в Threads."


comment_discovery = CommentDiscoveryService()
