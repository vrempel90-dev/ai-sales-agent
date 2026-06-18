import re
from difflib import SequenceMatcher

from app.agents import VIRAL_THREADS_TEMPLATES, viral_niche_post
from app.content_safety import validate_threads_post
from app.post_queue import PostQueue, QueuedPost

MIN_VIRAL_SCORE = 7

PAIN_WORDS = ("теря", "не дожд", "хаос", "медлен", "забы", "чёрная дыра", "устал",
              "не обработ", "не успева", "не занос", "пропада", "перегруж",
              "нет follow up", "ждать")
CONSEQUENCE_WORDS = ("ушёл", "уходит", "конкурент", "оплат", "потер", "не попал",
                     "без продаж", "исчез", "сгора", "не дожива", "не запис")
ECONOMIC_WORDS = ("деньг", "оплат", "реклам", "бюджет", "заяв", "время", "контрол",
                  "продаж", "лид", "клиент", "запис")
SOLUTION_WORDS = ("ai бот", "ai чат бот", "ai администратор", "ai менеджер")
SOLUTION_ACTIONS = ("отвечает", "уточняет", "собирает", "передаёт", "передает",
                    "создаёт заявку", "создает заявку", "напоминает", "доводит",
                    "квалифицирует", "фиксирует", "сохраняет", "принимает", "закрывает")
CHANNEL_WORDS = ("direct", "telegram", "whatsapp", "crm", "заяв", "follow up", "запис",
                 "админ", "клиент", "лид")
CTA_WORDS = ("напишите аудит", "напишите бот", "напишите разбор", "точки потерь")
WEAK_PHRASES = ("могу показать схему", "покажу простую схему", "если хотите расскажу",
                "давайте посмотрим", "могу предложить", "уникальный ai бот",
                "бесплатная услуга", "гарантированная прибыль", "просто улучшить",
                "поможет бизнесу", "развивайте бренд", "повышайте узнаваемость",
                "качественный контент", "индивидуальный подход", "мы лучшие",
                "команда профессионалов", "комплексный маркетинг")
IRRELEVANT = ("сайт", "лендинг", "веб-приложение", "html", "css", "javascript",
              "интернет-магазин", "seo", "дизайн сайта", "smm", "тестовая система",
              "бесконтактные технологии")
FRAGMENT_LINES = ("клиент написал", "контакт остаётся в telegram", "человек нужен для",
                  "клиент спросил цену")
WHATSAPP_MARKERS = ("https://wa.me/", "whatsapp_contact_link", "whatsapp_phone")


def normalize_thread_text(text: str) -> str:
    return re.sub(r"[^a-zа-яё0-9]+", " ", (text or "").lower()).strip()


def has_strong_cta(text: str) -> bool:
    normalized = normalize_thread_text(text)
    has_action = any(word in normalized for word in CTA_WORDS)
    has_destination = any(word in normalized for word in ("личку", "telegram", "direct", "whatsapp", "бот", "разбор"))
    return has_action and has_destination and not any(phrase in normalized for phrase in WEAK_PHRASES)


def has_specific_ai_solution(text: str) -> bool:
    normalized = normalize_thread_text(text)
    return (
        any(word in normalized for word in SOLUTION_WORDS)
        and any(action in normalized for action in SOLUTION_ACTIONS)
    )


def is_senior_marketing_post(text: str) -> bool:
    normalized = normalize_thread_text(text)
    first_line = next((line.strip() for line in (text or "").splitlines() if line.strip()), "")
    return all((
        bool(first_line) and len(first_line) <= 110,
        any(word in normalize_thread_text(first_line) for word in PAIN_WORDS + CONSEQUENCE_WORDS),
        any(word in normalized for word in PAIN_WORDS),
        any(word in normalized for word in CONSEQUENCE_WORDS),
        any(word in normalized for word in ECONOMIC_WORDS),
        has_specific_ai_solution(text),
        any(word in normalized for word in CHANNEL_WORDS),
        has_strong_cta(text),
        not any(phrase in normalized for phrase in WEAK_PHRASES),
        not any(phrase in normalized for phrase in IRRELEVANT),
    ))


def is_truncated_or_fragmented(text: str) -> bool:
    stripped = (text or "").strip()
    lines = [line.strip() for line in stripped.splitlines() if line.strip()]
    if len(stripped) < 250 or any(normalize_thread_text(line) in FRAGMENT_LINES for line in lines):
        return True
    if not stripped.endswith((".", "!", "?", "»")):
        return True
    return bool(re.search(r"\b(для|и|или|что|чтобы|потому что|если|когда)\s*[.!?…]?$", stripped.lower()))


def validate_growth_post(text: str) -> tuple[bool, str]:
    stripped = (text or "").strip()
    normalized = normalize_thread_text(stripped)
    if not 300 <= len(stripped) <= 700:
        return False, "длина должна быть 300–700 символов"
    paragraphs = [part.strip() for part in re.split(r"\n\s*\n", stripped) if part.strip()]
    if not 2 <= len(paragraphs) <= 4:
        return False, "нужно 2–4 абзаца"
    if is_truncated_or_fragmented(stripped):
        return False, "пост выглядит оборванным или фрагментированным"
    if any(marker in stripped.lower() for marker in WHATSAPP_MARKERS):
        return False, "WhatsApp-ссылка запрещена в публичном Threads-посте"
    if any(phrase in normalized for phrase in IRRELEVANT):
        return False, "запрещённая тема"
    if not has_specific_ai_solution(stripped):
        return False, "нет конкретного AI-бота как решения"
    if not any(word in normalized for word in PAIN_WORDS):
        return False, "нет боли владельца"
    if not any(word in normalized for word in CONSEQUENCE_WORDS):
        return False, "нет последствия"
    if not any(word in normalized for word in ECONOMIC_WORDS):
        return False, "нет коммерческого смысла"
    if not has_strong_cta(stripped):
        return False, "нет сильного CTA"
    if not is_senior_marketing_post(stripped):
        return False, "текст не проходит Senior Marketing Brain"
    valid, reason = validate_threads_post(stripped)
    return (valid, reason if not valid else "ok")


def score_thread_post(text: str) -> int:
    normalized = normalize_thread_text(text)
    if not normalized:
        return -20
    score = 0
    score += 2 if any(word in normalized for word in PAIN_WORDS) else -2
    score += 2 if any(word in normalized for word in CONSEQUENCE_WORDS) else -2
    score += 2 if has_specific_ai_solution(text) else -5
    score += 2 if any(word in normalized for word in ECONOMIC_WORDS) else -3
    score += 1 if any(word in normalized for word in CHANNEL_WORDS) else -1
    score += 4 if has_strong_cta(text) else -8
    first_line = next((line.strip() for line in (text or "").splitlines() if line.strip()), "")
    score += 1 if len(first_line) <= 100 and any(word in normalize_thread_text(first_line) for word in PAIN_WORDS + CONSEQUENCE_WORDS) else -1
    score += 1 if 300 <= len((text or "").strip()) <= 700 else -2
    score -= 5 * sum(phrase in normalized for phrase in WEAK_PHRASES)
    score -= 10 * sum(phrase in normalized for phrase in IRRELEVANT)
    score += 2 if is_senior_marketing_post(text) else -5
    if any(marker in (text or "").lower() for marker in WHATSAPP_MARKERS):
        return -20
    if not validate_growth_post(text)[0]:
        score -= 6
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
    valid, _ = validate_growth_post(candidate)
    if valid and score_thread_post(candidate) >= MIN_VIRAL_SCORE:
        return candidate
    fallback = viral_fallback(fallback_index, niche)
    valid, reason = validate_growth_post(fallback)
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
        if validate_growth_post(candidate)[0] and not is_duplicate_post(queue, candidate):
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
