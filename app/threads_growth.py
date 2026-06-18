import re
from difflib import SequenceMatcher

from app.agents import VIRAL_THREADS_TEMPLATES, viral_niche_post
from app.content_safety import validate_threads_post
from app.post_queue import PostQueue, QueuedPost

MIN_VIRAL_SCORE = 7

PAIN_WORDS = ("теря", "не дожд", "хаос", "медлен", "забы", "чёрная дыра", "устал", "не обработ")
CONSEQUENCE_WORDS = ("ушёл", "конкурент", "оплат", "потер", "не попал", "без продаж", "исчез")
SOLUTION_WORDS = ("ai бот", "ai чат бот", "ai администратор", "ai менеджер")
CHANNEL_WORDS = ("direct", "telegram", "whatsapp", "crm", "заяв", "follow-up", "запис")
CTA_WORDS = ("напишите аудит", "напишите бот", "напишите разбор", "точки потерь")
WEAK_PHRASES = ("могу показать схему", "уникальный ai-бот", "бесплатная услуга",
                "гарантированная прибыль", "просто улучшить", "поможет бизнесу")
IRRELEVANT = ("сайт", "лендинг", "веб-приложение", "html", "css", "javascript",
              "интернет-магазин", "seo", "дизайн сайта", "smm", "тестовая система")


def normalize_thread_text(text: str) -> str:
    return re.sub(r"[^a-zа-яё0-9]+", " ", (text or "").lower()).strip()


def score_thread_post(text: str) -> int:
    normalized = normalize_thread_text(text)
    if not normalized:
        return -20
    score = 0
    score += 2 if any(word in normalized for word in PAIN_WORDS) else -2
    score += 2 if any(word in normalized for word in CONSEQUENCE_WORDS) else -2
    score += 2 if any(word in normalized for word in SOLUTION_WORDS) else -4
    score += 1 if any(word in normalized for word in CHANNEL_WORDS) else -1
    score += 2 if any(word in normalized for word in CTA_WORDS) else -3
    first_line = next((line.strip() for line in (text or "").splitlines() if line.strip()), "")
    score += 1 if len(first_line) <= 100 and any(word in normalize_thread_text(first_line) for word in PAIN_WORDS + CONSEQUENCE_WORDS) else -1
    score += 1 if 300 <= len((text or "").strip()) <= 700 else -2
    score -= 5 * sum(phrase in normalized for phrase in WEAK_PHRASES)
    score -= 10 * sum(phrase in normalized for phrase in IRRELEVANT)
    return score


def posts_are_duplicates(left: str, right: str) -> bool:
    left_normalized = normalize_thread_text(left)
    right_normalized = normalize_thread_text(right)
    if left_normalized == right_normalized:
        return True
    left_prefix = left_normalized[:160]
    right_prefix = right_normalized[:160]
    return SequenceMatcher(None, left_prefix, right_prefix).ratio() >= 0.82


def is_duplicate_post(queue: PostQueue, text: str) -> bool:
    return any(posts_are_duplicates(text, post.text) for post in queue.list_active_and_published_today())


def viral_fallback(index: int = 0, niche: str | None = None) -> str:
    if niche:
        candidate = viral_niche_post(niche)
        if score_thread_post(candidate) >= MIN_VIRAL_SCORE:
            return candidate
    templates = list(VIRAL_THREADS_TEMPLATES)
    return templates[index % len(templates)]


def ensure_strong_post(text: str, fallback_index: int = 0, niche: str | None = None) -> str:
    candidate = (text or "").strip()
    valid, _ = validate_threads_post(candidate)
    if valid and score_thread_post(candidate) >= MIN_VIRAL_SCORE:
        return candidate
    fallback = viral_fallback(fallback_index, niche)
    valid, reason = validate_threads_post(fallback)
    if not valid or score_thread_post(fallback) < MIN_VIRAL_SCORE:
        raise ValueError(f"Некорректный viral fallback: {reason}")
    return fallback


def add_strong_unique_post(
    queue: PostQueue,
    text: str,
    *,
    source: str,
    fallback_index: int = 0,
    niche: str | None = None,
    scheduled_hour: int | None = None,
) -> QueuedPost | None:
    candidates = [ensure_strong_post(text, fallback_index, niche)]
    candidates.extend(viral_fallback(i) for i in range(len(VIRAL_THREADS_TEMPLATES)))
    for candidate in candidates:
        if not is_duplicate_post(queue, candidate):
            return queue.add_post(candidate, source=source, scheduled_hour=scheduled_hour)
    return None


def refill_growth_queue(queue: PostQueue, minimum: int, source: str = "growth-refill") -> list[QueuedPost]:
    added: list[QueuedPost] = []
    attempts = 0
    while queue.get_draft_count() < minimum and attempts < len(VIRAL_THREADS_TEMPLATES) * 2:
        post = add_strong_unique_post(
            queue,
            viral_fallback(attempts),
            source=source,
            fallback_index=attempts,
        )
        if post:
            added.append(post)
        attempts += 1
    return added


def best_publishable_post(queue: PostQueue) -> QueuedPost | None:
    posts = queue.list_publishable()
    return max(posts, key=lambda post: score_thread_post(post.text), default=None)
