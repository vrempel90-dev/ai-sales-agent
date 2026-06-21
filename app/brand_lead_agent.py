"""AI Brand & Lead Agent helpers for Threads.

Deterministic, Ollama-compatible helpers for brand sprint planning, hot lead
scoring and safe sales replies. No automatic DM/comment sending lives here.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import re
from typing import Iterable

from app.post_queue import PostQueue, QueuedPost

HOT_LEAD_KEYWORDS = (
    "сколько стоит", "цена", "прайс", "мне нужен бот", "нужен бот",
    "можно для салона", "для салона", "можно для клиники", "для клиники",
    "у нас заявки в директ", "заявки в direct", "заявки в директ",
    "хочу попробовать", "как подключить whatsapp", "как подключить ватсап",
    "можете сделать", "сделаете", "админ не успевает", "запись теряется",
    "заявка теряется", "напишите мне", "напишите в личку",
)
WARM_KEYWORDS = ("бот", "ai", "аи", "администратор", "direct", "директ", "whatsapp", "telegram", "заявки", "запись", "разбор")
PRICE_KEYWORDS = ("сколько стоит", "цена", "прайс", "стоимость", "дорого")
DEFAULT_CTA_KEYWORD = "разбор"

@dataclass(frozen=True)
class BrandDay:
    day: int
    stage: str
    theme: str
    goal: str
    posts: tuple[str, str, str]
    cta: str
    attracts: str
    lead_reaction: str
    niche: str
    sales_angle: str

BRAND_SPRINT: tuple[BrandDay, ...] = (
    BrandDay(1, "positioning", "Позиционирование: кто я и кому помогаю", "Чтобы люди поняли, что владелец делает AI-администраторов", ("Кто такой AI-автоматизатор и почему я смотрю не на ботов, а на путь заявки.", "Каким бизнесам с записью чаще всего нужен быстрый первый ответ.", "Почему Direct / WhatsApp / Telegram нельзя держать в голове администратора."), "Мягко: напишите «разбор», если хотите увидеть путь заявки", "владельцев услуг, которые уже получают входящие", "вопросы про нишу, Direct, WhatsApp или слово «разбор»", "салоны и услуги", "сначала показать экспертность, не продавать"),
    BrandDay(2, "pain_awareness", "Боль: заявки теряются до продажи", "Показать проблему", ("Клиент пропадает не после цены, а пока ждёт первый ответ.", "Где обычно ломается запись: Direct, админ, свободные окна, follow-up.", "Почему реклама может работать, а записей всё равно мало."), "Без жёсткого CTA: сохраните и проверьте свои входящие", "владельцев, которые чувствуют потери, но не видят точку", "сообщения про потерянные заявки, админа или скорость ответа", "салоны красоты", "признать потери до предложения решения"),
    BrandDay(3, "solution_explained", "AI-администратор как решение", "Объяснить простыми словами", ("AI-администратор — это первый ответ, уточнения и передача заявки человеку.", "Что бот может закрыть без замены команды: FAQ, запись, квалификация.", "Как выглядит путь заявки после подключения AI-администратора."), "Напишите «разбор» — покажу, что можно автоматизировать первым", "тёплых владельцев, которым нужен понятный сценарий", "вопросы «как работает», «можно для нас», «что подключать»", "клиники и стоматологии", "продать диагностику перед внедрением"),
    BrandDay(4, "niche_recognition", "Ниши: салон / клиника / услуги", "Чтобы бизнесы узнали себя", ("Салон теряет запись, когда клиент спрашивает окно и ждёт.", "Клиника теряет заявку, когда вопрос уходит между Direct и админом.", "Эксперт теряет оплату, когда нет быстрого follow-up."), "Если узнали свою ситуацию — напишите «разбор»", "салоны, клиники, косметологов, экспертов", "описание своей ниши или фраза «у нас так же»", "салоны / клиники / эксперты", "сделать проблему личной для ниши"),
    BrandDay(5, "objection_handling", "Возражения: цена, сложно, “у нас есть админ”", "Снять страхи", ("AI-администратор не заменяет хорошего админа, а снимает первый хаос.", "Почему начинать лучше не с большого бота, а с одной точки потери.", "Цена без диагностики обманывает: сначала каналы, CRM и сценарий."), "Можно начать с бесплатного разбора 3 точек потерь", "сомневающихся владельцев", "вопросы про цену, сложность, админа", "локальные услуги", "снизить риск и предложить маленький первый шаг"),
    BrandDay(6, "free_audit", "Бесплатный разбор", "Получить входящие", ("Бесплатно найду 3 места, где теряются заявки.", "Что я смотрю на разборе: канал, первый ответ, запись, follow-up.", "Кому разбор особенно полезен на этой неделе."), "Напишите «разбор»", "готовых на диагностику владельцев", "слово «разбор» или просьба написать", "косметологи и барбершопы", "вести в короткую диагностику"),
    BrandDay(7, "strong_cta", "Сильный CTA", "Собрать заявки", ("Если заявки есть, а записей мало — это можно быстро проверить.", "Не покупайте бота вслепую: сначала найдите потери.", "На этой неделе беру 5 разборов для бизнесов с Direct / WhatsApp."), "Напишите «разбор» — разберу 3 точки потери заявок", "самых горячих владельцев", "прямые заявки, цена, «можете сделать», «хочу попробовать»", "все ниши с записью", "создать срочность без гарантий и давления"),
)

def _setting(settings, name: str, default):
    return getattr(settings, name, default)

def current_sprint_day(settings) -> int:
    days = int(_setting(settings, "brand_lead_agent_sprint_days", 7) or 7)
    day = (datetime.now(timezone.utc).timetuple().tm_yday - 1) % max(1, days) + 1
    return min(day, len(BRAND_SPRINT))

def get_brand_day(day: int) -> BrandDay:
    return BRAND_SPRINT[max(1, min(day, len(BRAND_SPRINT))) - 1]

def build_brand_sprint(settings) -> str:
    lines = ["🧲 AI Brand & Lead Agent — 7-day client sprint", "Режим строит воронку и повышает шанс входящих: проблема → цена потерь → AI-решение → «разбор».\n"]
    for d in BRAND_SPRINT:
        lines.append(f"День {d.day}: {d.theme}\nЦель: {d.goal}\n3 поста:\n1. {d.posts[0]}\n2. {d.posts[1]}\n3. {d.posts[2]}\nCTA: {d.cta}\nКого привлекает: {d.attracts}\nРеакция-лид: {d.lead_reaction}")
    return "\n\n".join(lines)

def build_brand_today(settings) -> str:
    day = get_brand_day(current_sprint_day(settings))
    cta = _setting(settings, "brand_lead_agent_main_cta", "Напишите “разбор”")
    return (
        "AI Brand Plan Today:\n"
        f"Sprint day: {day.day}/7 — {day.stage}\n"
        f"Positioning message: {_setting(settings, 'brand_lead_agent_positioning', 'AI-автоматизатор для бизнесов, которые теряют заявки в Direct / WhatsApp / Telegram')}\n"
        f"Ниша дня: {day.niche}\n"
        f"Pain post idea: {day.posts[0]}\n"
        f"Trust post idea: {day.posts[1]}\n"
        f"Offer post idea: {day.posts[2]}\n"
        f"CTA of the day: {cta}\n"
        f"Expected inbound keyword: {DEFAULT_CTA_KEYWORD}\n"
        f"Best niche to target today: {day.niche}\n"
        f"Sales angle of the day: {day.sales_angle}\n"
        "What to answer if someone asks price: AI-администратор обычно начинается от 150 000 ₸, но сначала лучше сделать короткий разбор каналов, записи и follow-up."
    )

def build_brand_profile(settings) -> str:
    keyword = DEFAULT_CTA_KEYWORD
    return (
        "🧲 Упаковка Threads-профиля\n\n"
        "Имя / описание: AI-администраторы для салонов, клиник и услуг\n\n"
        "Bio:\nAI-администраторы для салонов, клиник и услуг.\nПомогаю не терять заявки из Direct / WhatsApp.\nНапиши “разбор” — найду 3 точки потери клиентов.\n\n"
        "Закреплённый пост:\nЯ делаю AI-администраторов для бизнесов, которые получают заявки в Direct, WhatsApp и Telegram. Сначала смотрю путь заявки: первый ответ, запись, CRM и follow-up. Потом показываю, что можно автоматизировать без давления и сложного внедрения.\n\n"
        "3 тезиса “чем помогаю”:\n1. Быстро найти, где теряются входящие заявки.\n2. Собрать сценарий AI-администратора под вашу нишу.\n3. Снизить хаос между Direct / WhatsApp / Telegram и записью.\n\n"
        f"CTA: Напишите “{keyword}” — бесплатно покажу 3 точки потери заявок.\n\n"
        "Первый комментарий под закрепом:\nЕсли хотите — пришлите нишу и куда приходят заявки. Я отвечу, с какой точки автоматизации лучше начать."
    )

def _contains_any(text: str, words: Iterable[str]) -> list[str]:
    n = (text or "").lower()
    return [w for w in words if w in n]

def is_price_question(text: str) -> bool:
    return bool(_contains_any(text, PRICE_KEYWORDS))

def score_lead(text: str) -> dict[str, object]:
    n = (text or "").lower().strip()
    hot = _contains_any(n, HOT_LEAD_KEYWORDS)
    warm = _contains_any(n, WARM_KEYWORDS)
    score = 12
    if warm:
        score = 45 + min(15, len(warm) * 5)
    if hot:
        score = 82 + min(15, len(hot) * 4)
    if any(x in n for x in ("салон", "клиник", "стомат", "космет", "барбер", "школ", "услуг")):
        score += 5
    score = max(0, min(100, score))
    temp = "cold / low" if score <= 30 else "warm interest" if score <= 60 else "potential client" if score <= 80 else "hot lead"
    why = ", ".join(hot or warm) if (hot or warm) else "нет явного бизнес-намерения или боли по заявкам"
    return {"score": score, "temperature": temp, "why": why, "handoff": score >= 80}

def build_lead_score(text: str) -> str:
    data = score_lead(text)
    reply = build_hot_reply(text) if data["score"] >= 61 else "Спасибо за интерес. Если актуальны заявки, запись или AI-администратор — напишите, куда сейчас приходят обращения."
    question = "Куда сейчас приходят заявки и кто отвечает первым?" if data["score"] >= 31 else "Есть ли у вас входящие заявки из Direct / WhatsApp / Telegram?"
    hot_note = "\n\n🔥 Горячий лид. Лучше отвечать вручную или через /client_reply и переводить в разбор." if data["score"] >= 80 else ""
    return (
        f"score: {data['score']}\n"
        f"lead temperature: {data['temperature']}\n"
        f"why: {data['why']}\n"
        f"next reply: {reply}\n"
        f"next question: {question}\n"
        f"should handoff to owner: {'yes' if data['handoff'] else 'no'}"
        f"{hot_note}"
    )

def build_hot_reply(text: str) -> str:
    price = is_price_question(text)
    prefix = "Для салона AI-администратор обычно начинается от 150 000 ₸. " if price else "Да, можно быстро посмотреть, подойдёт ли AI-администратор под вашу ситуацию. "
    return (
        prefix
        + "Но сначала лучше понять, где сейчас теряются заявки: Direct, WhatsApp, запись или ответы администратора. "
        + "Я могу сделать короткий разбор и сказать, какой вариант имеет смысл. "
        + "Куда сейчас приходят заявки и кто отвечает первым?"
    )

def brand_meta_for_text(text: str, settings) -> dict[str, str | int]:
    acq_goal = "offer" if "разбор" in (text or "").lower() and "напишите" in (text or "").lower() else "pain" if re.search(r"теря|пропада|жд", (text or "").lower()) else "trust"
    day = current_sprint_day(settings)
    sprint = get_brand_day(day)
    return {
        "brand_day": day,
        "sprint_stage": sprint.stage,
        "content_goal": acq_goal,
        "acquisition_stage": "conversion" if acq_goal == "offer" else "awareness" if acq_goal == "pain" else "trust",
        "cta_keyword": DEFAULT_CTA_KEYWORD if acq_goal == "offer" else "none",
        "lead_intent": "get_dm_with_keyword_razbor" if acq_goal == "offer" else "make_owner_recognize_lost_leads",
    }

def brand_report_block(settings, queue: PostQueue, current_week_leads: int = 0) -> str:
    enabled = bool(_setting(settings, "brand_lead_agent_enabled", True))
    day = get_brand_day(current_sprint_day(settings))
    return (
        "🧲 Brand & Lead Agent:\n"
        f"✅ mode: {'enabled' if enabled else 'disabled'}\n"
        f"Sprint day: {day.day}/{_setting(settings, 'brand_lead_agent_sprint_days', 7)}\n"
        f"Niche today: {day.niche}\n"
        f"CTA: “{_setting(settings, 'brand_lead_agent_main_cta', 'Напишите “разбор”')}”\n"
        f"posts planned: {_setting(settings, 'brand_lead_agent_daily_posts', 3)}\n"
        f"offer post planned: {'yes' if day.stage in {'free_audit', 'strong_cta', 'solution_explained'} else 'no'}\n"
        "hot lead keywords tracked: сколько стоит, нужен бот, салон, клиника, Direct, WhatsApp, админ не успевает\n"
        f"target leads this week: {_setting(settings, 'brand_lead_agent_target_leads_per_week', 5)}\n"
        f"current week leads: {current_week_leads}\n"
        f"recommendation for tomorrow: усилить пост про {day.niche}, Direct и скорость ответа"
    )
