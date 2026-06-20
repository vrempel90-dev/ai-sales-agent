import re
from difflib import SequenceMatcher

from app.agents import VIRAL_THREADS_TEMPLATES, viral_niche_post
from app.growth_content import GROWTH_TEMPLATES, GrowthTemplate
from collections import Counter
from datetime import datetime, timedelta, timezone
from app.content_safety import validate_threads_post
from app.post_queue import PostQueue, QueuedPost

from app.content_quality import (
    VIRAL_POST_MIN_SCORE as MIN_VIRAL_SCORE,
    CONTENT_REGENERATION_ATTEMPTS,
    build_metadata as build_quality_metadata,
    evaluate_post,
)

PAIN_WORDS = ("теря", "не дожд", "хаос", "медлен", "забы", "чёрная дыра", "устал",
              "не обработ", "не успева", "не занос", "пропада", "перегруж",
              "нет follow up", "ждать")
CONSEQUENCE_WORDS = ("ушёл", "уходит", "конкурент", "оплат", "потер", "не попал",
                     "без продаж", "несделанных продаж", "исчез", "сгора", "не дожива", "не запис")
ECONOMIC_WORDS = ("деньг", "оплат", "реклам", "бюджет", "заяв", "время", "контрол",
                  "продаж", "лид", "клиент", "запис")
SOLUTION_WORDS = ("ai бот", "ai чат бот", "ai администратор", "ai админ", "ai менеджер")
SOLUTION_ACTIONS = ("отвечает", "уточняет", "собирает", "передаёт", "передает",
                    "создаёт заявку", "создает заявку", "напоминает", "доводит",
                    "квалифицирует", "фиксирует", "сохраняет", "принимает", "принять", "закрывает", "закроет")
CHANNEL_WORDS = ("direct", "telegram", "whatsapp", "crm", "заяв", "follow up", "запис",
                 "админ", "клиент", "лид")
CTA_WORDS = ("напишите аудит", "напишите бот", "напишите разбор", "напишите схема", "точки потерь", "ответьте")
WEAK_PHRASES = ("покажу простую схему", "если хотите расскажу",
                "давайте посмотрим", "давайте рассмотрим", "могу предложить", "уникальный ai бот",
                "бесплатная услуга", "гарантированная прибыль", "просто улучшить",
                "поможет бизнесу", "развивайте бренд", "повышайте узнаваемость",
                "качественный контент", "индивидуальный подход", "мы лучшие",
                "команда профессионалов", "комплексный маркетинг", "автоматизируйте процессы",
                "повышайте эффективность", "наше решение позволит",
                "в современном бизнесе важно", "инструмент для оптимизации",
                "ai бот поможет вашему бизнесу")
IRRELEVANT = ("сайт", "лендинг", "веб-приложение", "html", "css", "javascript",
              "интернет-магазин", "seo", "дизайн сайта", "smm", "тестовая система",
              "бесконтактные технологии")
FRAGMENT_LINES = ("клиент написал", "контакт остаётся в telegram", "человек нужен для",
                  "клиент спросил цену")
WHATSAPP_MARKERS = ("https://wa.me/", "whatsapp_contact_link", "whatsapp_phone")
NUMBER_WORDS = {
    "ноль": "0", "один": "1", "одна": "1", "два": "2", "две": "2", "три": "3",
    "четыре": "4", "пять": "5", "шесть": "6", "семь": "7", "восемь": "8",
    "девять": "9", "десять": "10",
}
SYNONYMS = {
    "администратор": "админ", "администратора": "админ", "администратору": "админ",
    "администратором": "админ", "админа": "админ", "отвечал": "ответил", "ответила": "ответил",
    "ответили": "ответил", "отвечала": "ответил", "ушел": "ушёл", "уже": "",
}
HOOK_KEYWORDS = ("админ", "ответ", "клиент", "ушёл", "уходит", "час", "заяв", "лид", "медлен", "потер")


def normalize_thread_text(text: str) -> str:
    raw = re.sub(r"[^a-zа-яё0-9]+", " ", (text or "").lower()).strip()
    tokens = []
    for token in raw.split():
        token = NUMBER_WORDS.get(token, token)
        token = SYNONYMS.get(token, token)
        if token:
            tokens.append(token)
    return " ".join(tokens)


def extract_hook(text: str) -> str:
    first_line = next((line.strip() for line in (text or "").splitlines() if line.strip()), text or "")
    return normalize_thread_text(first_line[:180])


def _hook_signature(text: str) -> set[str]:
    hook = extract_hook(text)
    return {token for token in hook.split() if any(token.startswith(word) or word in token for word in HOOK_KEYWORDS)}


def has_strong_cta(text: str) -> bool:
    normalized = normalize_thread_text(text)
    has_action = any(word in normalized for word in CTA_WORDS)
    has_destination = any(word in normalized for word in ("личку", "telegram", "direct", "whatsapp", "бот", "разбор", "аудит", "схема", "crm"))
    return has_action and has_destination and not any(phrase in normalized for phrase in WEAK_PHRASES)


def has_specific_ai_solution(text: str) -> bool:
    normalized = normalize_thread_text(text)
    has_ai = any(word in normalized for word in SOLUTION_WORDS) or "ai админ" in normalized or "ai бот" in normalized
    has_action = any(action in normalized for action in SOLUTION_ACTIONS) or any(word in normalized for word in ("первый ответ", "follow up", "путь заявки", "закроет"))
    return has_ai and has_action


def is_not_banal_smm_post(text: str) -> bool:
    normalized = normalize_thread_text(text)
    first_line = next((line.strip() for line in (text or "").splitlines() if line.strip()), "")
    concrete = any(word in normalized for word in CHANNEL_WORDS + ("админ", "менеджер", "crm", "direct", "whatsapp", "telegram", "запис", "follow up"))
    human = any(word in normalized for word in ("я бы", "смешно", "проверьте", "часто", "обычно", "проблема", "владелец", "админ", "хорош", "пациент", "клиент"))
    value = any(word in normalized for word in ("проверь", "признак", "путь", "ошиб", "почему", "сначала", "места", "роль"))
    ad_like = any(phrase in normalized for phrase in WEAK_PHRASES)
    too_universal = not concrete
    return bool(first_line) and len(first_line) <= 140 and concrete and human and value and not ad_like and not too_universal


def is_senior_marketing_post(text: str) -> bool:
    normalized = normalize_thread_text(text)
    first_line = next((line.strip() for line in (text or "").splitlines() if line.strip()), "")
    return all((
        bool(first_line) and len(first_line) <= 140,
        any(word in normalized for word in ECONOMIC_WORDS),
        any(word in normalized for word in CHANNEL_WORDS),
        has_specific_ai_solution(text),
        has_strong_cta(text),
        is_not_banal_smm_post(text),
        not any(phrase in normalized for phrase in WEAK_PHRASES),
        not any((phrase != "сайт" and phrase in normalized) or (phrase == "сайт" and re.search(r"\bсайт\b", normalized)) for phrase in IRRELEVANT),
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
    if any((phrase != "сайт" and phrase in normalized) or (phrase == "сайт" and re.search(r"\bсайт\b", normalized)) for phrase in IRRELEVANT):
        return False, "запрещённая тема"
    if "существует рядом с" in normalized:
        return False, "нет конкретного AI-действия"
    if not (has_specific_ai_solution(stripped) or any(word in normalized for word in ("заяв", "клиент", "crm", "direct", "whatsapp", "telegram", "админ", "follow up"))):
        return False, "нет конкретики про заявки/каналы/CRM"
    if not any(word in normalized for word in ECONOMIC_WORDS + CHANNEL_WORDS):
        return False, "нет коммерческого или SMM-смысла"
    if not has_strong_cta(stripped):
        return False, "нет сильного CTA"
    if not is_not_banal_smm_post(stripped):
        return False, "банальный SMM-пост"
    valid, reason = validate_threads_post(stripped)
    return (valid, reason if not valid else "ok")


def score_thread_post(text: str) -> int:
    """0-100 viral score used by legacy tests and publishing priority."""
    score = build_quality_metadata(text).viral_score
    normalized = normalize_thread_text(text)
    first_line_raw = next((line.strip() for line in (text or "").splitlines() if line.strip()), "")
    first = normalize_thread_text(re.split(r"(?<=[.!?])\s+", first_line_raw, maxsplit=1)[0])
    if any(marker in (text or "").lower() for marker in WHATSAPP_MARKERS):
        score -= 40
    if not first.startswith("проверь") and not any(word in first for word in PAIN_WORDS + CONSEQUENCE_WORDS):
        score -= 12
    if not has_specific_ai_solution(text):
        score -= 20
    if not validate_growth_post(text)[0]:
        score -= 12
    return max(0, min(100, score))


def posts_are_duplicates(left: str, right: str) -> bool:
    left_normalized = normalize_thread_text(left)
    right_normalized = normalize_thread_text(right)
    if not left_normalized or not right_normalized:
        return False
    if left_normalized == right_normalized:
        return True
    left_prefix = left_normalized[:180]
    right_prefix = right_normalized[:180]
    if left_prefix == right_prefix or SequenceMatcher(None, left_prefix, right_prefix).ratio() >= 0.82:
        return True

    left_hook = extract_hook(left)
    right_hook = extract_hook(right)
    if left_hook and right_hook:
        hook_ratio = SequenceMatcher(None, left_hook, right_hook).ratio()
        left_signature = _hook_signature(left)
        right_signature = _hook_signature(right)
        overlap = left_signature & right_signature
        if hook_ratio >= 0.72 and len(overlap) >= 3:
            return True
        if {"админ", "клиент"}.issubset(overlap) and any(token.startswith("ответ") for token in overlap) and (
            "2" in overlap or any(token.startswith("час") for token in overlap) or any(token.startswith("уш") for token in overlap)
        ):
            return True
    return False


def duplicate_reference(queue: PostQueue, text: str) -> QueuedPost | None:
    for post in queue.list_duplicate_guard_posts():
        if posts_are_duplicates(text, post.text):
            return post
    return None


def is_duplicate_post(queue: PostQueue, text: str) -> bool:
    return duplicate_reference(queue, text) is not None



def template_for_text(text: str) -> GrowthTemplate | None:
    normalized = normalize_thread_text(text)
    return next((t for t in GROWTH_TEMPLATES if normalize_thread_text(t.text) == normalized), None)

def metadata_for_text(text: str) -> dict[str, str | int]:
    tpl = template_for_text(text)
    quality = build_quality_metadata(text)
    base = {"content_angle": quality.content_angle, "content_format": quality.content_format, "rubric": quality.content_format, "goal": "прогрев", "niche": quality.niche, "cta_type": quality.cta_type, "hook": quality.hook, "hook_type": quality.hook_type, "pain_angle": quality.pain_angle, "target_audience": quality.target_audience, "structure_type": quality.structure_type, "viral_score": quality.viral_score, "quality_score": quality.quality_score, "uniqueness_score": quality.uniqueness_score, "hash": quality.hash, "semantic_key": quality.semantic_key}
    if tpl:
        base.update({"content_angle": tpl.content_angle, "rubric": tpl.rubric, "goal": tpl.goal, "niche": tpl.niche})
    return base

def infer_cta_type(text: str) -> str:
    n = normalize_thread_text(text)
    for key in ("аудит", "бот", "разбор", "схема"):
        if key in n:
            return key
    return "личка"

def infer_content_angle(text: str) -> str:
    n = normalize_thread_text(text)
    checks = [("crm", "crm_not_filled"), ("follow up", "no_followup"), ("whatsapp", "whatsapp_chaos"), ("telegram", "telegram_without_crm"), ("ноч", "night_leads"), ("реклам", "ad_budget_lost"), ("замен", "ai_not_replace_manager"), ("админ", "admin_overloaded"), ("direct", "direct_chaos")]
    return next((angle for token, angle in checks if token in n), "simple_ai_admin_offer")

def angle_is_blocked(queue: PostQueue, angle: str, *, exclude_id: str | None = None) -> bool:
    from app.content_quality import CONTENT_MAX_SAME_ANGLE_IN_QUEUE, CONTENT_ANGLE_COOLDOWN_HOURS
    active = [p for p in queue.list_publishable() if str(p.id) != str(exclude_id)]
    if sum((p.content_angle or infer_content_angle(p.text)) == angle for p in active) > CONTENT_MAX_SAME_ANGLE_IN_QUEUE:
        return True
    cutoff = (datetime.now(timezone.utc) - timedelta(hours=CONTENT_ANGLE_COOLDOWN_HOURS)).isoformat()
    return any((p.content_angle or infer_content_angle(p.text)) == angle and (p.published_at or "") >= cutoff for p in queue.list_by_status("published"))

def queue_smm_quality(queue: PostQueue) -> dict[str, object]:
    posts = queue.list_publishable()
    angles = [p.content_angle or infer_content_angle(p.text) for p in posts]
    rubrics = [p.rubric or "Custom" for p in posts]
    ctas = [p.cta_type or infer_cta_type(p.text) for p in posts]
    repeated = [a for a,c in Counter(angles).items() if c > 1]
    banal = [p for p in posts if not is_not_banal_smm_post(p.text)]
    formats = sorted(set(rubrics))
    goals = [p.goal or metadata_for_text(p.text)["goal"] for p in posts]
    cta_repeats = any(ctas[i] == ctas[i-1] == ctas[i-2] for i in range(2, len(ctas)))
    format_repeats = any(rubrics[i] == rubrics[i-1] == rubrics[i-2] for i in range(2, len(rubrics)))
    risk = "high" if banal or cta_repeats or format_repeats or any(Counter(angles)[a] >= 3 for a in angles) else ("medium" if repeated or len(set(ctas)) < 2 else "low")
    return {"unique_angles": len(set(angles)), "repeated_angles": repeated, "rubrics": formats, "formats_count": len(formats), "cta_diversity": "good" if len(set(ctas)) >= 2 and not cta_repeats else "weak", "look_unique": not repeated and not banal, "template_risk": risk, "banal_count": len(banal), "has_trust": any(g in ("Trust", "Founder POV", "Proof") or "довер" in g.lower() for g in goals), "has_offer": any(g == "Offer" or c == "аудит" for g,c in zip(goals, ctas)), "has_expertise": any(g in ("Education", "Diagnostic", "Founder POV") for g in goals)}


def first_sentence(text: str) -> str:
    stripped = (text or "").strip()
    match = re.split(r"(?<=[.!?])\s+|\n+", stripped, maxsplit=1)
    return normalize_thread_text(match[0] if match else stripped)


def content_memory_blocks(queue: PostQueue, text: str, meta: dict[str, str]) -> tuple[bool, str]:
    recent_14 = queue.list_published_since(14) + queue.list_publishable()
    fs = first_sentence(text)
    if fs and any(first_sentence(p.text) == fs for p in recent_14):
        return True, "first_sentence repeated inside 14 days"
    cutoff = (datetime.now(timezone.utc) - timedelta(hours=48)).isoformat()
    if any((p.content_angle or infer_content_angle(p.text)) == meta["content_angle"] and (p.published_at or p.created_at or "") >= cutoff for p in recent_14):
        return True, "content_angle repeated inside 48h"
    active = queue.list_publishable()
    last_two = active[-2:]
    if len(last_two) == 2 and all((p.content_format or p.rubric or metadata_for_text(p.text)["content_format"]) == meta["content_format"] for p in last_two):
        return True, "content_format repeated more than 2 times"
    if len(last_two) == 2 and all((p.cta_type or infer_cta_type(p.text)) == meta["cta_type"] for p in last_two):
        return True, "cta_type repeated more than 2 times"
    return False, "ok"

def viral_fallback(index: int = 0, niche: str | None = None) -> str:
    if niche:
        candidate = viral_niche_post(niche)
        if build_quality_metadata(candidate).viral_score >= MIN_VIRAL_SCORE:
            return candidate
    templates = list(VIRAL_THREADS_TEMPLATES)
    return templates[index % len(templates)]


def ensure_strong_post(text: str, fallback_index: int = 0, niche: str | None = None) -> str:
    candidate = (text or "").strip()
    valid, _ = validate_growth_post(candidate)
    if valid and build_quality_metadata(candidate).viral_score >= MIN_VIRAL_SCORE:
        return candidate
    for offset in range(len(VIRAL_THREADS_TEMPLATES)):
        fallback = viral_fallback(fallback_index + offset, niche)
        valid, reason = validate_growth_post(fallback)
        if valid and build_quality_metadata(fallback).viral_score >= MIN_VIRAL_SCORE:
            return fallback
    raise ValueError(f"Некорректный viral fallback: {reason}")


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
    # Up to 3 regeneration attempts with different template angles, then fallback rubric sweep.
    candidates.extend(viral_fallback(fallback_index + i + 1) for i in range(CONTENT_REGENERATION_ATTEMPTS))
    candidates.extend(viral_fallback(i) for i in range(len(VIRAL_THREADS_TEMPLATES)))
    seen_candidates: set[str] = set()
    last_reason = "weak_quality_score"
    for candidate in candidates:
        if normalize_thread_text(candidate) in seen_candidates:
            continue
        seen_candidates.add(normalize_thread_text(candidate))
        meta = metadata_for_text(candidate)
        result = evaluate_post(queue, candidate, meta)
        if not result.accepted:
            last_reason = result.reason
            queue.record_duplicate_skip(candidate, source=source, reason=result.reason)
            continue
        return queue.add_post(candidate, source=source, scheduled_hour=scheduled_hour, **meta)
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


def rebuild_growth_queue(queue: PostQueue, minimum: int, source: str = "growth-rebuild") -> dict[str, object]:
    generated_before = queue.get_draft_count()
    removed_duplicates = purge_duplicate_drafts(queue)
    removed_weak = 0
    removed_banal = 0
    removed_angle = 0
    seen_angles: set[str] = set()
    for post in queue.list_publishable():
        angle = post.content_angle or infer_content_angle(post.text)
        quality_result = evaluate_post(queue, post.text, metadata_for_text(post.text), exclude_id=post.id)
        if not quality_result.accepted and quality_result.reason in {"robotic_text", "weak_viral_score", "weak_quality_score"}:
            queue.mark_duplicate_skipped(post.id, reason=quality_result.reason)
            removed_banal += 1
            removed_weak += 1
        elif not quality_result.accepted or build_quality_metadata(post.text).viral_score < MIN_VIRAL_SCORE or angle in seen_angles:
            queue.mark_duplicate_skipped(post.id, reason="weak or repeated angle rebuild")
            removed_angle += 1 if angle in seen_angles else 0
            removed_weak += 1
        else:
            seen_angles.add(angle)
    before = queue.get_draft_count()
    added = refill_growth_queue(queue, minimum, source=source)
    quality = queue_smm_quality(queue)
    posts = queue.list_publishable()
    avg = lambda name: round(sum((getattr(p, name) or metadata_for_text(p.text)[name]) for p in posts) / len(posts), 1) if posts else 0
    return {"generated": generated_before + len(added), "accepted": len(added), "rejected_duplicates": removed_duplicates + removed_angle, "rejected_weak": removed_weak, "removed_duplicates": removed_duplicates, "removed_weak": removed_weak, "added": len(added), "rubrics": quality["rubrics"], "angles": sorted({p.content_angle or infer_content_angle(p.text) for p in posts}), "unique_angles": len({p.content_angle or infer_content_angle(p.text) for p in posts}), "avg_viral_score": avg("viral_score"), "avg_quality_score": avg("quality_score"), "avg_uniqueness_score": avg("uniqueness_score"), "before": before, "removed_banal": removed_banal, "removed_angle": removed_angle, "robot_like_risk": quality["template_risk"]}


def purge_duplicate_drafts(queue: PostQueue) -> int:
    skipped = 0
    seen: list[QueuedPost] = []
    for post in queue.list_publishable():
        duplicate = next((item for item in seen if posts_are_duplicates(post.text, item.text)), None)
        if duplicate is not None:
            queue.mark_duplicate_skipped(post.id, duplicate_text=post.text, reason=f"duplicate of queued #{duplicate.id}")
            skipped += 1
        else:
            seen.append(post)
    return skipped


def best_publishable_post(queue: PostQueue) -> QueuedPost | None:
    purge_duplicate_drafts(queue)
    posts = queue.list_publishable()
    return max(posts, key=lambda post: score_thread_post(post.text), default=None)


def next_unique_publishable_post(queue: PostQueue) -> QueuedPost | None:
    for post in queue.list_publishable():
        duplicate = queue.find_duplicate_for_publish(post.id, post.text)
        if duplicate:
            queue.mark_duplicate_skipped(post.id, reason=f"duplicate of published #{duplicate.id}")
    for post in sorted(queue.list_publishable(), key=lambda item: (item.viral_score or score_thread_post(item.text)), reverse=True):
        duplicate = queue.find_duplicate_for_publish(post.id, post.text)
        if duplicate is None:
            return post
        queue.mark_duplicate_skipped(post.id, duplicate_text=post.text, reason=f"duplicate of published #{duplicate.id}")
    return None
