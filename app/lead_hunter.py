from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
import hashlib
import re

SAFE_SOURCE_NOTE = "queue-first/manual-send: no scraping, no browser emulation, no mass DM"
MANUAL_NO_CHANNEL_MESSAGE = "Автоотправка недоступна: нет официального канала DM. Сообщение подготовлено для ручной отправки."

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
AGGRESSIVE_MARKERS = ("купите", "срочно", "гарантирую", "у вас плохо", "у вас плохо работает", "скидка только сегодня")
PRICE_RE = re.compile(r"\b\d{2,}[\s\d]*(?:₸|тг|тенге|руб|₽|\$)\b", re.I)
LINK_RE = re.compile(r"https?://|wa\.me|api\.whatsapp", re.I)
TELEGRAM_CHAT_RE = re.compile(r"(?:telegram_chat_id|tg_chat_id|chat_id)\s*[:=]\s*(-?\d+)", re.I)

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
    channel: str = ""
    contact: str = ""
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

@dataclass
class SentHistoryItem:
    lead_id: str
    message_text: str
    channel: str
    sent_at: str
    status: str
    score: int
    niche: str
    source: str

@dataclass
class LeadHunterRuntime:
    items: list[HunterLead] = field(default_factory=list)
    scanned_count: int = 0
    added_count: int = 0
    sent_dates: list[str] = field(default_factory=list)
    sent_history: list[SentHistoryItem] = field(default_factory=list)
    hot_replies: int = 0
    last_action: str = "нет действий"
    last_error: str = "нет"
    autopilot_override: bool | None = None
    blocked_no_channel: int = 0
    blocked_safety: int = 0
    blocked_daily_limit: int = 0

    def reset(self):
        self.items.clear(); self.scanned_count = 0; self.added_count = 0; self.sent_dates.clear(); self.sent_history.clear(); self.hot_replies = 0; self.last_action = "нет действий"; self.last_error = "нет"; self.autopilot_override = None; self.blocked_no_channel = 0; self.blocked_safety = 0; self.blocked_daily_limit = 0

    def drafts(self):
        return [i for i in self.items if i.status in {"draft", "ready_for_manual_send"}]

    def ready_for_manual_send_count(self):
        return sum(1 for i in self.items if i.status == "ready_for_manual_send")

    def sent_today(self):
        today = datetime.now(timezone.utc).date().isoformat()
        return sum(1 for d in self.sent_dates if d == today)

    def enabled(self, configured: bool) -> bool:
        return configured if self.autopilot_override is None else self.autopilot_override

lead_hunter = LeadHunterRuntime()

def _contains(text, markers): return any(m in text for m in markers)

def detect_niche(text: str) -> str:
    low = text.lower()
    for niche, markers in FIT_NICHES.items():
        if _contains(low, markers): return niche
    return "неясная ниша"

def detect_official_channel(text: str, allowed_channels: str = "telegram") -> tuple[str, str]:
    allowed = {c.strip().lower() for c in (allowed_channels or "").split(",") if c.strip()}
    match = TELEGRAM_CHAT_RE.search(text or "")
    if "telegram" in allowed and match:
        return "telegram", match.group(1)
    return "", ""

def official_channel_available(lead: HunterLead | None = None, allowed_channels: str = "telegram") -> bool:
    if lead is None:
        return False
    channel, contact = detect_official_channel(lead.source_text, allowed_channels)
    return channel == "telegram" and bool(contact)

def draft_message(niche: str, text: str) -> str:
    if niche == "салон красоты":
        return "Здравствуйте. Увидел, что у вас услуги идут через запись. Часто в таких нишах часть клиентов теряется в Direct, когда админ отвечает не сразу или не доводит до записи. Могу показать, как AI-администратор закрывает первый ответ и помогает не терять заявки."
    if niche in {"клиника", "стоматология"}:
        return f"Здравствуйте. У {niche} часто теряются обращения ещё до записи: человек пишет, ждёт ответ и уходит к другим. Я занимаюсь AI-администраторами, которые отвечают первыми, уточняют запрос и передают заявку администратору. Могу показать схему под вашу нишу."
    if niche == "онлайн-школа":
        return "Здравствуйте. Если заявки приходят в Direct или Telegram, часть диалогов может теряться без follow-up. AI-бот может отвечать первым, квалифицировать человека и передавать тёплую заявку. Могу показать короткую схему."
    return "Здравствуйте. Увидел, что у вас есть услуги и входящие обращения. В таких бизнесах часть заявок теряется, когда ответ или follow-up делаются вручную. Могу показать короткую схему, как AI-администратор отвечает первым и передаёт тёплую заявку."

def message_is_safe(message: str, recent_messages: list[str] | None = None, require_personalization: bool = True) -> tuple[bool, str]:
    low = message.lower()
    if LINK_RE.search(message): return False, "first message must not contain WhatsApp/link"
    if PRICE_RE.search(message): return False, "first message must not contain price"
    if _contains(low, AGGRESSIVE_MARKERS): return False, "aggressive sales phrase"
    if len(message) > 600: return False, "message too long"
    if "ai-администратор" not in low and "ai-бот" not in low: return False, "AI help must be clear"
    if "могу показать" not in low: return False, "soft CTA is required"
    if require_personalization and not any(n in low for n in FIT_NICHES) and "услуг" not in low:
        return False, "message lacks niche personalization"
    if recent_messages and message.strip() in [m.strip() for m in recent_messages[-5:]]:
        return False, "duplicate message text"
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
    safe, reason = message_is_safe(msg, require_personalization=False)
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
    channel, contact = detect_official_channel(text)
    lead = HunterLead(fp, text[:500], str(data["niche"]), int(data["score"]), str(data["pain_hypothesis"]), str(data["why"]), str(data["draft_message"]), channel=channel, contact=contact)
    lead_hunter.items.append(lead); lead_hunter.added_count += 1; lead_hunter.last_action = f"lead queued #{lead.id}"
    return data, lead, "queued"

def next_lead():
    return next((i for i in lead_hunter.items if i.status == "draft"), None)

def mark_skip(lead_id: str) -> bool:
    for i in lead_hunter.items:
        if i.id == lead_id: i.status = "skipped"; lead_hunter.last_action = f"lead skipped #{lead_id}"; return True
    return False

def recently_contacted(lead: HunterLead) -> bool:
    threshold = datetime.now(timezone.utc) - timedelta(days=14)
    for item in lead_hunter.sent_history:
        if item.source == lead.source_text:
            try:
                if datetime.fromisoformat(item.sent_at) >= threshold:
                    return True
            except ValueError:
                return True
    return False

def record_sent(lead: HunterLead, channel: str) -> None:
    now = datetime.now(timezone.utc)
    lead.status = "sent"
    lead_hunter.sent_dates.append(now.date().isoformat())
    lead_hunter.sent_history.append(SentHistoryItem(lead.id, lead.draft_message, channel, now.isoformat(), "sent", lead.score, lead.niche, lead.source_text))
    lead_hunter.last_action = f"official DM sent #{lead.id} via {channel}"
    lead_hunter.last_error = "нет"

def send_or_prepare(lead_id: str, *, min_score: int, daily_limit: int, approval_required: bool, auto_dm_enabled: bool, allowed_channels: str = "telegram", require_personalization: bool = True, block_if_no_official_channel: bool = True, confirmed: bool = False) -> tuple[bool, str]:
    lead = next((i for i in lead_hunter.items if i.id == lead_id), None)
    if not lead: return False, "Лид не найден."
    if lead.score < min_score: return False, "Score ниже минимального."
    recent = [i.message_text for i in lead_hunter.sent_history[-5:]]
    safe, reason = message_is_safe(lead.draft_message, recent, require_personalization)
    if not safe:
        lead_hunter.blocked_safety += 1; lead_hunter.last_error = "failed safety guard"; return False, f"Safety guard: {reason}. Regenerate сообщение."
    if recently_contacted(lead): return False, "Anti-spam guard: этому источнику уже писали за последние 14 дней."
    if lead_hunter.sent_today() >= daily_limit:
        lead_hunter.blocked_daily_limit += 1; lead_hunter.last_error = "blocked by daily limit"; return False, "Дневной лимит исчерпан."
    if approval_required and not confirmed:
        lead.status = "ready_for_manual_send"; lead_hunter.last_action = f"approval required #{lead.id}"; return False, f"Требуется подтверждение владельца: /lead_confirm_send {lead.id}\n\n{lead.draft_message}"
    channel, contact = detect_official_channel(lead.source_text, allowed_channels)
    if not auto_dm_enabled or not channel or (block_if_no_official_channel and not contact):
        lead.status = "ready_for_manual_send"; lead_hunter.blocked_no_channel += 1 if not channel else 0; lead_hunter.last_action = f"manual send prepared #{lead.id}"; return False, f"{MANUAL_NO_CHANNEL_MESSAGE}\n\n{lead.draft_message}"
    record_sent(lead, channel)
    return True, f"Отправлено через официальный канал {channel}: {contact}"

def prepare_send(lead_id: str, *, min_score: int, daily_limit: int, approval_required: bool, auto_dm_enabled: bool, allowed_channels: str = "telegram", require_personalization: bool = True, block_if_no_official_channel: bool = True) -> tuple[bool, str]:
    return send_or_prepare(lead_id, min_score=min_score, daily_limit=daily_limit, approval_required=approval_required, auto_dm_enabled=auto_dm_enabled, allowed_channels=allowed_channels, require_personalization=require_personalization, block_if_no_official_channel=block_if_no_official_channel)

def run_autopilot_once(*, enabled: bool, min_score: int, daily_limit: int, auto_dm_enabled: bool, approval_required: bool, allowed_channels: str, require_personalization: bool, block_if_no_official_channel: bool) -> tuple[bool, str]:
    if not lead_hunter.enabled(enabled): return False, "Lead Outreach Autopilot выключен."
    lead = next_lead()
    if not lead: return False, "Нет подходящих лидов в outreach queue."
    return send_or_prepare(lead.id, min_score=min_score, daily_limit=daily_limit, approval_required=approval_required, auto_dm_enabled=auto_dm_enabled, allowed_channels=allowed_channels, require_personalization=require_personalization, block_if_no_official_channel=block_if_no_official_channel, confirmed=not approval_required)

def lead_hunter_reply_notification(niche: str, pain: str, score: int, customer_message: str) -> str:
    return ("🔥 Ответил потенциальный клиент\n\nИсточник: Lead Hunter\n" f"Ниша: {niche}\nПроблема: {pain}\nLead score: {score}\nСообщение клиента: {customer_message}\nРекомендуемый следующий шаг: Sales Closing Agent квалифицирует cold/warm/hot; hot lead вести в WhatsApp и уведомить владельца.")
