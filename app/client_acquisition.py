"""Client Acquisition Mode for AI Growth Marketer.

Deterministic helpers for daily pain → trust → offer content, profile offers,
client replies and report metadata. The module is intentionally local-template
first so /offer_post and reports work even when Ollama is unavailable.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import re

from app.content_quality import evaluate_post
from app.post_queue import PostQueue, QueuedPost

DEFAULT_MAIN_KEYWORD = "разбор"
DEFAULT_SECONDARY_KEYWORDS = "бот,AI,админ,заявки,цена,сколько стоит"
DEFAULT_TARGET_NICHES = "салон красоты,клиника,стоматология,косметолог,барбершоп,онлайн-школа,эксперт,локальные услуги"
INBOUND_KEYWORDS = (
    "разбор", "бот", "ai", "аи", "админ", "администратор", "заявки", "заявка",
    "цена", "сколько стоит", "директ", "direct", "whatsapp", "ватсап", "telegram", "телеграм", "запись",
)
FORBIDDEN_OFFER_PHRASES = ("купите", "гарантир", "100%", "ссылка", "http://", "https://", "₸", "тенге")

@dataclass(frozen=True)
class AcquisitionMeta:
    content_goal: str
    acquisition_stage: str
    cta_keyword: str


def acquisition_meta_for_text(text: str) -> AcquisitionMeta:
    n = (text or "").lower()
    if "напишите" in n and "разбор" in n and "3" in n:
        return AcquisitionMeta("offer", "conversion", "разбор")
    if any(w in n for w in ("crm", "сначала", "почему", "не в рекламе", "follow-up")):
        return AcquisitionMeta("expert", "trust", "none")
    if any(w in n for w in ("теря", "пропада", "жд", "ушёл", "уходит", "40 минут")):
        return AcquisitionMeta("pain", "awareness", "none")
    return AcquisitionMeta("expert", "trust", "none")


def build_pain_post() -> str:
    return (
        "Клиент не пропадает после цены. Он пропадает раньше — когда ждёт ответ 40 минут.\n\n"
        "Владелец видит только тех, кто дошёл до записи. А часть людей уже написала в Direct, WhatsApp или Telegram, не получила быстрый первый ответ и ушла к конкуренту.\n\n"
        "AI-администратор закрывает этот первый участок: отвечает сразу, уточняет запрос и передаёт диалог человеку без хаоса."
    )


def build_expert_post() -> str:
    return (
        "CRM не спасает заявку, если она до CRM не дошла.\n\n"
        "Чаще проблема не в рекламе, а в обработке первого сообщения: кто ответил, где сохранили контакт, кто напомнил клиенту после вопроса о цене.\n\n"
        "Сначала нужно закрыть первый ответ и follow-up. AI-администратор фиксирует заявку из Direct, WhatsApp или Telegram и передаёт её в понятный следующий шаг."
    )


def build_offer_post(keyword: str = DEFAULT_MAIN_KEYWORD) -> str:
    keyword = (keyword or DEFAULT_MAIN_KEYWORD).strip() or DEFAULT_MAIN_KEYWORD
    return (
        "Если у вас салон, клиника или услуга по записи — проверьте одну вещь.\n\n"
        "Сколько клиентов написали вам в Direct и не дошли до записи?\n\n"
        "Чаще всего проблема не в рекламе. Проблема в первом ответе, свободных окнах, follow-up и хаосе между Direct/WhatsApp/админом.\n\n"
        "Могу бесплатно найти 3 места, где ваш бизнес теряет заявки, и показать, что можно закрыть AI-администратором.\n\n"
        f"Напишите «{keyword}» — сделаю короткий разбор без навязчивой продажи."
    )


def build_audit_offer(keyword: str = DEFAULT_MAIN_KEYWORD) -> str:
    keyword = keyword or DEFAULT_MAIN_KEYWORD
    return (
        "Короткий оффер для поста:\n"
        "Бесплатно найду 3 места, где ваш бизнес теряет заявки в Direct / WhatsApp / Telegram, и покажу, что может закрыть AI-администратор.\n\n"
        "Био:\n"
        f"AI-администраторы для салонов, клиник и услуг. Помогаю не терять заявки из Direct/WhatsApp. Напиши «{keyword}» — найду 3 точки потери клиентов.\n\n"
        "Закреп:\n"
        "Я делаю AI-администраторов для бизнесов, которые теряют заявки в Direct, WhatsApp и Telegram. Сначала смотрю путь заявки: первый ответ, запись, CRM и follow-up. Потом показываю, что можно автоматизировать без ломки процесса.\n\n"
        "CTA для комментариев:\n"
        f"Напишите «{keyword}» — покажу, где у вас теряются заявки."
    )


def build_profile_offer(keyword: str = DEFAULT_MAIN_KEYWORD) -> str:
    keyword = keyword or DEFAULT_MAIN_KEYWORD
    return (
        "Bio Threads:\n"
        f"AI-администраторы для бизнесов с записью. Помогаю не терять заявки из Direct, WhatsApp и Telegram. Напиши «{keyword}» — найду 3 точки потери клиентов.\n\n"
        "Закреплённый пост:\n"
        "Если клиент написал и не дошёл до записи — это не всегда проблема рекламы. Часто заявка теряется раньше: долгий первый ответ, свободные окна в голове администратора, нет follow-up, контакт не попал в CRM. Я делаю AI-администраторов, которые закрывают этот первый хаос и передают команде понятный диалог.\n\n"
        "Короткое описание услуги:\n"
        "AI-администратор отвечает первым, уточняет запрос, помогает с записью, фиксирует контакт и передаёт заявку человеку или в CRM.\n\n"
        "CTA:\n"
        f"Напишите «{keyword}» — бесплатно покажу 3 места, где у вас теряются заявки."
    )


def has_inbound_signal(text: str) -> bool:
    n = (text or "").lower()
    return any(k in n for k in INBOUND_KEYWORDS)


def build_client_reply(message: str) -> str:
    n = (message or "").lower()
    if "сайт" in n or "лендинг" in n:
        return (
            "Сайты и лендинги не моя основная специализация. Я занимаюсь AI-ботами и автоматизацией обработки заявок: Direct, WhatsApp, Telegram, запись, CRM и follow-up. "
            "Если задача именно не терять входящие обращения — могу быстро посмотреть ваш путь заявки и сказать, где AI-администратор будет полезен."
        )
    if "разбор" in n:
        return (
            "Да, давайте начнём с короткой диагностики без продажи. Ответьте, пожалуйста:\n"
            "1. Какая у вас ниша?\n2. Куда сейчас приходят заявки?\n3. Кто отвечает клиентам?\n4. Есть CRM или запись вручную?\n\n"
            "После этого покажу 3 места, где могут теряться клиенты, и что можно закрыть AI-администратором."
        )
    if "сколько стоит" in n or "цена" in n or "дорого" in n:
        return (
            "Обычно AI-администратор начинается от 150 000 ₸. Точную стоимость не называю без диагностики: она зависит от каналов, CRM, записи и сценария. "
            "Сначала я бы быстро посмотрел: куда приходят заявки, кто отвечает и где чаще теряются клиенты. Могу сделать короткий бесплатный разбор и сказать, какой вариант подойдёт."
        )
    if has_inbound_signal(message):
        return (
            "Понял задачу. Чтобы не предлагать лишнее, уточню 3 вещи: какая у вас ниша, куда приходят заявки — Direct/WhatsApp/Telegram, и кто сейчас отвечает клиентам? "
            "После этого покажу, где может теряться заявка и какой сценарий AI-администратора подойдёт."
        )
    return "Могу помочь, если задача связана с AI-администратором, заявками, записью или обработкой входящих. Опишите, где сейчас теряются клиенты."


def offer_posts_today(queue: PostQueue) -> list[QueuedPost]:
    today = datetime.now(timezone.utc).date().isoformat()
    return [p for p in queue.list_active_and_published_today() if acquisition_meta_for_text(p.text).content_goal == "offer" and (p.created_at or p.published_at or "").startswith(today)]


def add_daily_acquisition_posts(queue: PostQueue, *, offer_hour: int = 18, keyword: str = DEFAULT_MAIN_KEYWORD) -> list[QueuedPost]:
    posts: list[QueuedPost] = []
    for text, hour, goal, stage, cta in [
        (build_pain_post(), 10, "pain", "awareness", "none"),
        (build_expert_post(), 14, "expert", "trust", "none"),
    ]:
        result = evaluate_post(queue, text, {"content_angle": f"client_acquisition_{goal}", "content_format": goal, "cta_type": cta})
        if result.accepted:
            meta = result.metadata.__dict__.copy(); meta.pop("text", None)
            meta.update({"goal": goal, "content_format": goal, "content_angle": f"client_acquisition_{goal}", "cta_type": cta, "generation_source": "client_acquisition"})
            posts.append(queue.add_post(text, source="client-acquisition", scheduled_hour=hour, **meta))
    if not offer_posts_today(queue):
        text = build_offer_post(keyword)
        result = evaluate_post(queue, text, {"content_angle": "free_audit", "content_format": "direct_offer", "cta_type": "ask_audit"})
        if result.accepted:
            meta = result.metadata.__dict__.copy(); meta.pop("text", None)
            meta.update({"goal": "offer", "content_format": "direct_offer", "content_angle": "free_audit", "cta_type": "ask_audit", "generation_source": "client_acquisition"})
            posts.append(queue.add_post(text, source="client-acquisition", scheduled_hour=offer_hour, **meta))
    return posts


def client_acquisition_report_block(settings, queue: PostQueue) -> str:
    active = queue.list_publishable()
    offer_count = sum(1 for p in active if acquisition_meta_for_text(p.text).content_goal == "offer")
    posts_to_dm = any(acquisition_meta_for_text(p.text).cta_keyword != "none" for p in active)
    keyword = getattr(settings, "client_acquisition_main_keyword", DEFAULT_MAIN_KEYWORD)
    enabled = getattr(settings, "client_acquisition_mode_enabled", True)
    return (
        "🎯 Client Acquisition:\n"
        f"✅ mode: {'enabled' if enabled else 'disabled'}\n"
        f"✅ offer post today: {'yes' if offer_posts_today(queue) else 'no'}\n"
        f"CTA: “напишите {keyword}”\n"
        "Inbound keywords tracked: разбор, бот, цена, заявки\n"
        f"Offer posts in queue: {offer_count}\n"
        f"Posts leading to DM: {'yes' if posts_to_dm else 'no'}\n"
        "Client replies prepared: 0\n"
        "Recommendation: завтра усилить нишу салонов и клиник"
    )
