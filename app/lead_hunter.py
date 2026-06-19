from dataclasses import dataclass, field
from datetime import datetime, timezone
import hashlib
import re

SAFE_SOURCE_NOTE = "queue-first/manual-send: no scraping, no browser emulation, no mass DM"

FIT_NICHES = {
    "салон красоты": ("салон", "маникюр", "косметолог", "бров", "ресниц", "парикмах", "барбер", "beauty", "nails"),
    "клиника": ("клиник", "медцентр", "врач", "пациент", "прием", "приём", "консультац"),
    "стоматология": ("стоматолог", "зуб", "ортодонт"),
    "онлайн-школа": ("онлайн-школ", "курс", "обучен", "вебинар", "наставник"),
    "эксперт": ("эксперт", "консультац", "коуч", "психолог", "нутрициолог"),
    "локальные услуги": ("ремонт", "строитель", "клининг", "сервис", "услуг", "мастер"),
    "фитнес": ("фитнес", "тренер", "зал", "студия", "йога", "пилатес"),
}
BUSINESS_MARKERS = ("услуг", "запис", "консультац", "клиент", "прайс", "адрес", "график", "заказ", "бронь")
CHANNEL_MARKERS = ("direct", "директ", "whatsapp", "ватсап", "wa.me", "telegram", "телеграм", "тг", "личк")
PAIN_MARKERS = ("заяв", "запис", "админ", "отвеч", "сообщ", "директ", "follow-up", "фоллоу", "теря", "не успева")
ACTIVITY_MARKERS = ("пост", "сторис", "комментар", "отзыв", "акция", "новинка", "сегодня", "ежеднев")
BAD_MARKERS = ("политик", "религи", "токсич", "18+", "казино", "ставки", "личный блог", "несовершеннолет", "школьник", "конкурент", "боты для бизнеса")
AGGRESSIVE_MARKERS = ("купите", "срочно", "гарантирую", "у вас плохо", "скидка только сегодня")
PRICE_RE = re.compile(r"\b\d{2,}[\s\d]*(?:₸|тг|тенге|руб|₽|\$)\b", re.I)
LINK_RE = re.compile(r"https?://|wa\.me|api\.whatsapp", re.I)

@dataclass
class HunterLead:
    id: str
    source_text: str
    niche: str
    score: int
    pain_hypothesis: str
    reason: str
    draft_message: str
    status: str = "draft"
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

@dataclass
class LeadHunterRuntime:
    items: list[HunterLead] = field(default_factory=list)
    scanned_count: int = 0
    added_count: int = 0
    sent_dates: list[str] = field(default_factory=list)
    hot_replies: int = 0
    last_action: str = "нет действий"
    last_error: str = "нет"

    def reset(self):
        self.items.clear(); self.scanned_count = 0; self.added_count = 0; self.sent_dates.clear(); self.hot_replies = 0; self.last_action = "нет действий"; self.last_error = "нет"

    def drafts(self):
        return [i for i in self.items if i.status in {"draft", "ready_for_manual_send"}]

    def sent_today(self):
        today = datetime.now(timezone.utc).date().isoformat()
        return sum(1 for d in self.sent_dates if d == today)

lead_hunter = LeadHunterRuntime()

def _contains(text, markers): return any(m in text for m in markers)

def detect_niche(text: str) -> str:
    low = text.lower()
    for niche, markers in FIT_NICHES.items():
        if _contains(low, markers): return niche
    return "неясная ниша"

def draft_message(niche: str, text: str) -> str:
    if niche == "салон красоты":
        return "Здравствуйте. Увидел, что у вас услуги идут через запись. Часто в таких нишах часть клиентов теряется в Direct, когда админ отвечает не сразу или не доводит до записи. Могу показать, как AI-администратор закрывает первый ответ и помогает не терять заявки."
    if niche in {"клиника", "стоматология"}:
        return f"Здравствуйте. У {niche} часто теряются обращения ещё до записи: человек пишет, ждёт ответ и уходит к другим. Я занимаюсь AI-администраторами, которые отвечают первыми, уточняют запрос и передают заявку администратору. Могу показать схему под вашу нишу."
    if niche == "онлайн-школа":
        return "Здравствуйте. Если заявки приходят в Direct или Telegram, часть диалогов может теряться без follow-up. AI-бот может отвечать первым, квалифицировать человека и передавать тёплую заявку. Могу показать короткую схему."
    return "Здравствуйте. Увидел, что у вас есть услуги и входящие обращения. В таких бизнесах часть заявок теряется, когда ответ или follow-up делаются вручную. Могу показать короткую схему, как AI-администратор отвечает первым и передаёт тёплую заявку."

def message_is_safe(message: str) -> tuple[bool, str]:
    low = message.lower()
    if LINK_RE.search(message): return False, "first message must not contain links"
    if PRICE_RE.search(message): return False, "first message must not contain price"
    if _contains(low, AGGRESSIVE_MARKERS): return False, "aggressive sales phrase"
    if len(message) > 650: return False, "message too long"
    return True, "ok"

def analyze_candidate(text: str) -> dict[str, object]:
    low = " ".join((text or "").lower().split())
    niche = detect_niche(low)
    score = 0; plus=[]; minus=[]
    if niche != "неясная ниша": score += 25; plus.append("подходящая ниша")
    else: minus.append("неясная ниша")
    if _contains(low, BUSINESS_MARKERS): score += 20; plus.append("есть признаки бизнеса/услуг")
    else: minus.append("нет явных услуг")
    if _contains(low, CHANNEL_MARKERS): score += 15; plus.append("есть Direct/WhatsApp/Telegram")
    else: minus.append("канал заявок не указан")
    if _contains(low, PAIN_MARKERS): score += 20; plus.append("видна боль заявок/записи/ответов")
    else: minus.append("боль с заявками не очевидна")
    if _contains(low, ACTIVITY_MARKERS): score += 10; plus.append("есть активность")
    if len(low) > 60: score += 10; plus.append("достаточно данных для персонализации")
    else: minus.append("мало данных для персонализации")
    if _contains(low, BAD_MARKERS): score -= 50; minus.append("неподходящая/рискованная тема")
    score = max(0, min(100, score))
    msg = draft_message(niche, text)
    safe, reason = message_is_safe(msg)
    if not safe:
        score = min(score, 69); minus.append(reason)
    pain = "может терять заявки из-за ручного ответа, записи и отсутствия follow-up" if score >= 70 else "боль не подтверждена"
    return {"niche": niche, "score": score, "pain_hypothesis": pain, "why": "; ".join(plus + minus), "draft_message": msg, "safe": safe}

def fingerprint(text: str) -> str:
    return hashlib.sha1(" ".join((text or "").lower().split()).encode()).hexdigest()[:10]

def add_candidate(text: str, min_score: int) -> tuple[dict[str, object], HunterLead | None, str]:
    lead_hunter.scanned_count += 1
    data = analyze_candidate(text)
    fp = fingerprint(text)
    if any(i.id == fp or i.draft_message == data["draft_message"] for i in lead_hunter.items):
        lead_hunter.last_action = "duplicate lead skipped"
        return data, None, "duplicate"
    if int(data["score"]) < min_score:
        lead_hunter.last_action = "lead scanned but not queued"
        return data, None, "below_min_score"
    lead = HunterLead(fp, text[:500], str(data["niche"]), int(data["score"]), str(data["pain_hypothesis"]), str(data["why"]), str(data["draft_message"]))
    lead_hunter.items.append(lead); lead_hunter.added_count += 1; lead_hunter.last_action = f"lead queued #{lead.id}"
    return data, lead, "queued"

def next_lead():
    return next((i for i in lead_hunter.items if i.status == "draft"), None)

def mark_skip(lead_id: str) -> bool:
    for i in lead_hunter.items:
        if i.id == lead_id: i.status = "skipped"; lead_hunter.last_action = f"lead skipped #{lead_id}"; return True
    return False

def prepare_send(lead_id: str, *, min_score: int, daily_limit: int, approval_required: bool, auto_dm_enabled: bool) -> tuple[bool, str]:
    lead = next((i for i in lead_hunter.items if i.id == lead_id), None)
    if not lead: return False, "Лид не найден."
    if lead.score < min_score: return False, "Score ниже минимального."
    safe, reason = message_is_safe(lead.draft_message)
    if not safe: return False, f"Safety guard: {reason}"
    if lead_hunter.sent_today() >= daily_limit: return False, "Дневной лимит исчерпан."
    if approval_required or not auto_dm_enabled:
        lead.status = "ready_for_manual_send"; lead_hunter.last_action = f"manual send prepared #{lead.id}"
        return False, f"Авто-отправки DM нет. Отправьте вручную после подтверждения:\n\n{lead.draft_message}"
    return False, "DM integration disabled by safety architecture. Manual send only."

def lead_hunter_reply_notification(niche: str, pain: str, score: int, customer_message: str) -> str:
    return ("🔥 Ответил потенциальный клиент\n\nИсточник: Lead Hunter\n" f"Ниша: {niche}\nПроблема: {pain}\nLead score: {score}\nСообщение клиента: {customer_message}\nРекомендуемый следующий шаг: Sales Closing Agent квалифицирует cold/warm/hot; hot lead вести в WhatsApp и уведомить владельца.")
