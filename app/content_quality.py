"""Viral Content Quality System for Threads drafts.

Checks exact, semantic, angle, structure/CTA duplicates and rejects weak AI-like posts
before queueing and before publishing. The module is deterministic so it works with
local templates and survives redeploys through PostQueue's SQLite history tables.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from difflib import SequenceMatcher
import hashlib
import os
import re

VIRAL_POST_MIN_SCORE = int(os.getenv("VIRAL_POST_MIN_SCORE", "75"))
CONTENT_QUALITY_MIN_SCORE = int(os.getenv("CONTENT_QUALITY_MIN_SCORE", "80"))
CONTENT_UNIQUENESS_MIN_SCORE = int(os.getenv("CONTENT_UNIQUENESS_MIN_SCORE", "85"))
CONTENT_MAX_SAME_ANGLE_IN_QUEUE = int(os.getenv("CONTENT_MAX_SAME_ANGLE_IN_QUEUE", "1"))
CONTENT_ANGLE_COOLDOWN_HOURS = int(os.getenv("CONTENT_ANGLE_COOLDOWN_HOURS", "48"))
CONTENT_CTA_COOLDOWN_COUNT = int(os.getenv("CONTENT_CTA_COOLDOWN_COUNT", "2"))
CONTENT_STRUCTURE_COOLDOWN_COUNT = int(os.getenv("CONTENT_STRUCTURE_COOLDOWN_COUNT", "2"))
CONTENT_REGENERATION_ATTEMPTS = int(os.getenv("CONTENT_REGENERATION_ATTEMPTS", "3"))
CONTENT_HISTORY_DAYS = int(os.getenv("CONTENT_HISTORY_DAYS", "14"))
CONTENT_BLOCK_GENERIC_AI_POSTS = os.getenv("CONTENT_BLOCK_GENERIC_AI_POSTS", "true").lower() in {"1", "true", "yes", "on"}

WEAK_STARTS = (
    "в современном бизнесе", "ai становится важным инструментом", "автоматизация помогает",
    "каждый бизнес хочет", "если вы хотите улучшить", "ai боты это будущее",
)
GENERIC_PHRASES = WEAK_STARTS + ("помогает бизнесу", "автоматизировать процессы", "улучшить сервис", "повышайте эффективность")
PAIN = ("теря", "пропада", "не дожд", "медлен", "хаос", "забы", "перегруж", "не успева", "follow up", "не занос", "ждёт", "ушёл")
MONEY = ("деньг", "реклам", "бюджет", "продаж", "оплат", "заяв", "лид", "клиент")
SPECIFIC = ("direct", "whatsapp", "telegram", "crm", "админ", "администратор", "салон", "клиник", "стомат", "запис", "цена", "ноч", "40 минут", "15 минут")
CTA_MAP = {"ask_audit": ("аудит",), "ask_scheme": ("схема",), "write_bot": ("бот",), "ask_3_losses": ("3 пот", "три пот"), "ask_example": ("пример",), "soft_dm": ("личку", "direct")}

@dataclass
class PostMetadata:
    post_id: str | None = None
    text: str = ""
    hook: str = ""
    hook_type: str = "pain_hook"
    content_format: str = "observation"
    content_angle: str = "manual_booking"
    pain_angle: str = "slow_response"
    niche: str = "общий бизнес"
    target_audience: str = "owners"
    cta_type: str = "soft_dm"
    structure_type: str = "short_observation"
    viral_score: int = 0
    uniqueness_score: int = 0
    quality_score: int = 0
    created_at: str | None = None
    published_at: str | None = None
    status: str = "draft"
    semantic_key: str = ""
    hash: str = ""

@dataclass
class QualityResult:
    accepted: bool
    reason: str = "ok"
    metadata: PostMetadata = field(default_factory=PostMetadata)
    checks: list[str] = field(default_factory=list)


def normalize_text(text: str) -> str:
    return re.sub(r"[^a-zа-яё0-9]+", " ", (text or "").lower()).strip()

def first_words(text: str, count: int = 10) -> str:
    return " ".join(normalize_text(text).split()[:count])

def final_phrase(text: str) -> str:
    parts = [p.strip() for p in re.split(r"[.!?\n]+", text or "") if p.strip()]
    return normalize_text(parts[-1]) if parts else ""

def hook(text: str) -> str:
    return next((l.strip() for l in (text or "").splitlines() if l.strip()), (text or "").strip())[:160]

def infer_hook_type(text: str) -> str:
    h = normalize_text(hook(text))
    if "?" in hook(text): return "question_hook"
    if any(w in h for w in ("миф", "замен")): return "myth_hook"
    if any(w in h for w in ("ошиб", "не начина")): return "mistake_hook"
    if any(w in h for w in ("деньг", "бюджет", "реклам")): return "money_loss_hook"
    if any(w in h for w in ("проверь", "признак")): return "checklist_hook"
    if any(w in h for w in ("салон", "клиник", "кейс")): return "case_hook"
    if any(w in h for w in ("не ", "а ", "не проблема")): return "contrarian_hook"
    return "pain_hook"

def infer_cta_type(text: str) -> str:
    n = normalize_text(text)
    for cta, keys in CTA_MAP.items():
        if any(k in n for k in keys): return cta
    if "ответьте" in n or "коммент" in n: return "comment_keyword"
    return "no_cta"

def infer_structure_type(text: str) -> str:
    n = normalize_text(text); paras = [p for p in re.split(r"\n\s*\n", text.strip()) if p.strip()]
    if re.search(r"\b[1-5]\b|первое|второе|третье|признак", n): return "checklist"
    if "миф" in n: return "myth_truth"
    if any(w in n for w in ("было", "стало", "до ", "после")): return "before_after"
    if any(w in n for w in ("салон", "клиник", "пациент")): return "mini_story"
    if "ошиб" in n or "не начина" in n: return "mistake_explanation"
    if "напишите" in n and len(paras) <= 3: return "direct_offer"
    if hook(text).startswith("Я бы"): return "founder_note"
    if "проверь" in n or "сколько" in n: return "diagnostic_questions"
    return "problem_consequence_solution" if len(paras) >= 3 else "short_observation"

def infer_angle(text: str) -> str:
    n = normalize_text(text)
    checks = [("direct", "direct_chaos"), ("whatsapp", "whatsapp_chaos"), ("follow up", "no_followup"), ("crm", "crm_not_filled"), ("ноч", "night_leads_lost"), ("реклам", "ads_budget_lost"), ("цена", "client_asked_price_and_left"), ("салон", "salon_booking"), ("клиник", "clinic_booking"), ("стомат", "dentist_booking"), ("замен", "ai_not_replace_admin"), ("аудит", "audit_offer"), ("админ", "admin_overloaded")]
    return next((a for k, a in checks if k in n), "manual_booking")

def infer_content_format(text: str) -> str:
    st = infer_structure_type(text); n = normalize_text(text)
    if "миф" in n: return "myth"
    if st == "checklist": return "checklist"
    if "ошиб" in n: return "mistake"
    if st == "mini_story": return "mini_case"
    if "не начина" in n: return "anti_advice"
    if "проверь" in n: return "diagnosis"
    if st == "direct_offer": return "direct_offer"
    if st == "founder_note": return "founder_pov"
    return "pain" if any(w in n for w in PAIN) else "observation"

def semantic_key(text: str) -> str:
    n = normalize_text(text)
    tokens = [w for w in n.split() if len(w) > 3 and any(k in w for k in PAIN + MONEY + SPECIFIC)]
    return " ".join(sorted(set(tokens))[:12]) or infer_angle(text)

def score_viral(text: str) -> int:
    n = normalize_text(text); h = hook(text); score = 45
    score += 10 if len(h) <= 100 and any(w in normalize_text(h) for w in PAIN + MONEY) else -10
    score += 10 if any(w in n for w in PAIN) else -15
    score += 8 if any(w in n for w in MONEY) else -8
    score += 18 if any(w in n for w in SPECIFIC) else -8
    score += 6 if any(w in n for w in ("а не", "не замен", "сначала", "раньше", "важнее")) else 0
    score += 12 if infer_cta_type(text) != "no_cta" else -10
    score += 5 if 250 <= len(text.strip()) <= 750 else -8
    score += 15 if sum(1 for w in SPECIFIC if w in n) >= 3 else 0
    score -= 12 * sum(p in n for p in GENERIC_PHRASES)
    return max(0, min(100, score))

def score_quality(text: str) -> int:
    n = normalize_text(text); score = 50
    score += 10 if len(hook(text)) <= 140 else -8
    score += 10 if any(w in n for w in PAIN) else -12
    score += 10 if any(w in n for w in SPECIFIC) else -10
    score += 8 if any(w in n for w in MONEY) else -5
    score += 7 if infer_cta_type(text) != "no_cta" else -10
    score += 5 if not any(p in n for p in GENERIC_PHRASES) else -20
    score += 5 if not re.search(r"как ai|как искусственный интеллект|инновацион", n) else -8
    return max(0, min(100, score))

def build_metadata(text: str, **overrides) -> PostMetadata:
    n = normalize_text(text); h = hook(text)
    meta = PostMetadata(text=text.strip(), hook=h, hook_type=infer_hook_type(text), content_format=infer_content_format(text), content_angle=infer_angle(text), pain_angle=semantic_key(text).split(" ")[0] if semantic_key(text) else "general", niche=("салон" if "салон" in n else "клиника" if "клиник" in n else "общий бизнес"), cta_type=infer_cta_type(text), structure_type=infer_structure_type(text), viral_score=score_viral(text), quality_score=score_quality(text), semantic_key=semantic_key(text), hash=hashlib.sha256(n.encode()).hexdigest())
    for k, v in overrides.items():
        if hasattr(meta, k) and v is not None: setattr(meta, k, v)
    return meta

def similarity(a: str, b: str) -> float:
    return SequenceMatcher(None, normalize_text(a), normalize_text(b)).ratio()

def semantic_duplicate(a: str, b: str) -> bool:
    ma, mb = build_metadata(a), build_metadata(b)
    key_overlap = set(ma.semantic_key.split()) & set(mb.semantic_key.split())
    return ma.content_angle == mb.content_angle and len(key_overlap) >= 2

def evaluate_post(queue, text: str, metadata: dict | None = None, *, exclude_id: str | None = None) -> QualityResult:
    meta = build_metadata(text, **(metadata or {})); refs = queue.list_content_history(days=CONTENT_HISTORY_DAYS, include_skipped=False) if hasattr(queue, "list_content_history") else queue.list_duplicate_guard_posts()
    refs = [p for p in refs if str(getattr(p, "id", getattr(p, "post_id", ""))) != str(exclude_id)]
    for p in refs:
        pt = p.text
        if normalize_text(pt) == normalize_text(text) or similarity(pt, text) >= 0.88 or first_words(pt) == first_words(text):
            meta.uniqueness_score = 20; return QualityResult(False, "exact_duplicate", meta, ["exact"])
        # Repeated final phrases are weak, but shared short CTA templates are allowed
        # when angle/hook/structure are different; consecutive CTA checks below catch runs.
        if final_phrase(pt) and final_phrase(pt) == final_phrase(text) and len(final_phrase(text).split()) > 16:
            meta.uniqueness_score = 60; return QualityResult(False, "same_cta", meta, ["final_phrase"])
        if semantic_duplicate(pt, text):
            meta.uniqueness_score = 55; return QualityResult(False, "semantic_duplicate", meta, ["semantic"])
    active = queue.list_publishable()
    if sum((getattr(p, "content_angle", None) or infer_angle(p.text)) == meta.content_angle for p in active if str(p.id) != str(exclude_id)) > CONTENT_MAX_SAME_ANGLE_IN_QUEUE:
        meta.uniqueness_score = 60; return QualityResult(False, "angle_duplicate", meta, ["queue_angle"])
    cutoff = (datetime.now(timezone.utc) - timedelta(hours=CONTENT_ANGLE_COOLDOWN_HOURS)).isoformat()
    if any((getattr(p, "content_angle", None) or infer_angle(p.text)) == meta.content_angle and (p.published_at or "") >= cutoff for p in queue.list_by_status("published")):
        meta.uniqueness_score = 60; return QualityResult(False, "angle_duplicate", meta, ["published_angle"])
    last = active[-CONTENT_CTA_COOLDOWN_COUNT:]
    if len(last) >= CONTENT_CTA_COOLDOWN_COUNT and all((p.cta_type or infer_cta_type(p.text)) == meta.cta_type for p in last):
        meta.uniqueness_score = 70; return QualityResult(False, "same_cta", meta, ["cta_run"])
    if len(last) >= CONTENT_STRUCTURE_COOLDOWN_COUNT and all((getattr(p, "structure_type", None) or infer_structure_type(p.text)) == meta.structure_type for p in last):
        meta.uniqueness_score = 70; return QualityResult(False, "same_structure", meta, ["structure_run"])
    if CONTENT_BLOCK_GENERIC_AI_POSTS and any(p in normalize_text(text) for p in GENERIC_PHRASES):
        meta.uniqueness_score = 80; return QualityResult(False, "robotic_text", meta, ["generic"])
    if meta.viral_score < VIRAL_POST_MIN_SCORE: return QualityResult(False, "weak_viral_score", meta, ["viral"])
    if meta.quality_score < CONTENT_QUALITY_MIN_SCORE: return QualityResult(False, "weak_quality_score", meta, ["quality"])
    meta.uniqueness_score = 100 if not refs else max(85, 100 - int(max((similarity(text, p.text) for p in refs), default=0) * 20))
    if meta.uniqueness_score < CONTENT_UNIQUENESS_MIN_SCORE: return QualityResult(False, "low_uniqueness_score", meta, ["uniqueness"])
    return QualityResult(True, "ok", meta, ["accepted"])
