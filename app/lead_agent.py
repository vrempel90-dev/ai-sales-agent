from dataclasses import dataclass
import re


PRICE_RANGES = (
    "Простой AI-бот / AI-ответчик — от 150 000 ₸",
    "AI-администратор для заявок — 150 000–300 000 ₸",
    "AI-бот с Telegram / WhatsApp / CRM / записью — 300 000–700 000 ₸",
    "Сложный AI-агент под бизнес-процессы — от 700 000 ₸",
    "Поддержка — 30 000–100 000 ₸/мес",
)
HOT_LEAD_THRESHOLD = 5

SITE_MARKERS = ("сайт", "лендинг", "web-прилож", "веб-прилож", "html", "css", "javascript", "интернет-магазин", "seo", "дизайн сайта")
PRICE_MARKERS = ("цена", "стоимость", "сколько стоит", "прайс", "бюджет")
PAYMENT_MARKERS = ("как оплатить", "хочу оплатить", "готов оплатить", "куда оплатить", "оплата сейчас")
NEGATIVE_MARKERS = ("не интересно", "неинтересно", "отстаньте", "не пишите", "спам", "ерунда", "бред")
ACTION_MARKERS = ("хочу бота", "хочу ai-бота", "нужен бот", "нужно сделать", "давайте делать", "хочу заказать", "как начать", "давайте обсудим", "готов обсудить", "когда нач", "срок", "созвон")
PAIN_MARKERS = ("теря", "долго отвеч", "не успева", "вручную", "пропада", "много заяв", "нет записи", "админ", "рутин", "не отвечает")
CHANNELS = {
    "Instagram/Direct": ("instagram", "инстаграм", "direct", "директ"),
    "WhatsApp": ("whatsapp", "ватсап", "вотсап"),
    "Telegram": ("telegram", "телеграм"),
    "CRM": ("crm", "црм"),
    "сайт": ("сайт",),
}
NICHES = {
    "салон красоты": ("салон", "маникюр", "косметолог", "парикмах", "барбершоп"),
    "клиника": ("клиник", "стоматолог", "медцентр"),
    "ресторан": ("ресторан", "кафе"),
    "магазин": ("магазин", "товар"),
    "онлайн-школа": ("школ", "курс", "обучен"),
    "услуги": ("услуг",),
}


@dataclass(frozen=True)
class LeadReply:
    text: str
    stage: str
    lead_score: str
    score: int
    next_step: str
    summary: str
    recommended_price: str
    is_hot: bool = False


def _contains(text: str, markers: tuple[str, ...]) -> bool:
    return any(marker in text for marker in markers)


def _find_label(text: str, mapping: dict[str, tuple[str, ...]], fallback: str) -> str:
    for label, markers in mapping.items():
        if _contains(text, markers):
            return label
    return fallback


def contact_destination(contact_link: str, phone: str) -> str | None:
    return contact_link.strip() or phone.strip() or None


def analyze_lead(message: str) -> dict[str, object]:
    text = " ".join((message or "").lower().split())
    niche = _find_label(text, NICHES, "не уточнена")
    channel = _find_label(text, CHANNELS, "не уточнён")
    has_price = _contains(text, PRICE_MARKERS)
    has_action = _contains(text, ACTION_MARKERS)
    has_pain = _contains(text, PAIN_MARKERS)
    wants_payment = _contains(text, PAYMENT_MARKERS)

    score = 0
    score += 2 if niche != "не уточнена" else 0
    score += 1 if channel != "не уточнён" else 0
    score += 2 if has_pain else 0
    score += 3 if has_action else 0
    score += 1 if has_price else 0
    score += 2 if wants_payment else 0
    lead_score = "hot" if score >= HOT_LEAD_THRESHOLD or wants_payment else "warm" if score >= 2 or has_price else "cold"
    return {
        "text": text,
        "niche": niche,
        "channel": channel,
        "has_price": has_price,
        "has_action": has_action,
        "has_pain": has_pain,
        "wants_payment": wants_payment,
        "score": score,
        "lead_score": lead_score,
    }


def _recommended_price(data: dict[str, object]) -> str:
    text = str(data["text"])
    if _contains(text, ("crm", "црм", "запис", "несколько канал", "telegram", "whatsapp")):
        return "300 000–700 000 ₸"
    if _contains(text, ("администратор", "заяв", "салон", "клиник")):
        return "150 000–300 000 ₸"
    return "от 150 000 ₸"


def _summary(data: dict[str, object], message: str) -> str:
    pain = "описана реальная проблема" if data["has_pain"] else "не уточнена"
    budget = "интересуется стоимостью" if data["has_price"] else "не уточнён"
    request = re.sub(r"\s+", " ", message).strip()[:180] or "интерес к AI-боту"
    return (
        f"Ниша: {data['niche']}\n"
        f"Запрос: {request}\n"
        f"Боль: {pain}\n"
        f"Канал: {data['channel']}\n"
        f"Бюджет: {budget}\n"
        f"Рекомендуемый чек: {_recommended_price(data)}"
    )


def classify_stage(message: str) -> str:
    data = analyze_lead(message)
    text = str(data["text"])
    if _contains(text, SITE_MARKERS):
        return "irrelevant_site_request"
    if _contains(text, NEGATIVE_MARKERS):
        return "negative"
    if data["wants_payment"]:
        return "payment_handoff"
    if data["lead_score"] == "hot":
        return "hot_lead"
    if data["has_price"]:
        return "price_question"
    if data["niche"] != "не уточнена" or data["channel"] != "не уточнён":
        return "business_described"
    return "new_interest"


def build_lead_reply(message: str, contact_link: str = "", phone: str = "") -> LeadReply:
    data = analyze_lead(message)
    stage = classify_stage(message)
    destination = contact_destination(contact_link, phone)
    recommended_price = _recommended_price(data)
    summary = _summary(data, message)
    is_hot = stage in {"hot_lead", "payment_handoff"}

    if stage == "irrelevant_site_request":
        text = (
            "Сайты не делаю. Я специализируюсь на AI-чат-ботах и автоматизации заявок. "
            "Могу показать, как бот будет принимать обращения из Direct, Telegram или WhatsApp, "
            "уточнять запрос и передавать вам тёплую заявку."
        )
        next_step = "Уточнить канал входящих заявок и предложить AI-бота"
    elif stage == "payment_handoff":
        text = "Отлично. Я передам вас владельцу, он уточнит детали и даст финальное подтверждение по цене и срокам."
        if destination:
            text += f"\n\nДля продолжения можно перейти в WhatsApp: {destination}"
        next_step = "Владельцу связаться с лидом и подтвердить цену и сроки"
    elif stage == "price_question":
        text = (
            "Если коротко: простой AI-бот начинается от 150 000 ₸.\n\n"
            "Точная стоимость зависит от задачи: где приходят заявки, что бот должен делать, "
            "нужна ли CRM, запись или несколько каналов. Я сначала быстро разберу процесс и "
            "после этого владелец подтвердит точную стоимость.\n\n"
            "Для какой ниши нужен бот и где сейчас приходят заявки?"
        )
        next_step = "Уточнить нишу и канал заявок"
    elif stage == "hot_lead":
        niche = str(data["niche"])
        if niche == "салон красоты":
            value = (
                "Для салона это сильный кейс: AI-бот отвечает сразу, уточняет услугу, "
                "собирает контакт, помогает с записью и передаёт тёплую заявку."
            )
        elif niche == "клиника":
            value = (
                "Для клиники AI-администратор может уточнять запрос пациента, отвечать на "
                "частые вопросы, помогать с записью и передавать заявку администратору."
            )
        else:
            value = "AI-бот может сразу обработать обращение, уточнить потребность и передать вам тёплую заявку."
        handoff = f"Перейдём в WhatsApp, чтобы быстро разобрать процесс: {destination}" if destination else "Оставьте номер или удобный контакт — владелец свяжется с вами и уточнит детали."
        text = f"Понял. {value}\n\n{handoff}"
        next_step = "Написать клиенту в WhatsApp" if destination else "Получить контакт и передать владельцу"
    elif stage == "negative":
        text = "Понимаю, не буду навязываться. Если захотите убрать ручную обработку заявок, подскажу безопасный сценарий AI-бота."
        next_step = "Не продолжать продажу без нового интереса клиента"
    elif str(data["niche"]) == "салон красоты":
        text = (
            "Понял, для салона это как раз сильный кейс.\n\n"
            "Обычно заявки теряются так: клиент пишет в Direct, админ отвечает поздно, "
            "после вопроса о цене диалог останавливается. AI-бот может ответить сразу, "
            "уточнить услугу, собрать контакт, предложить запись и передать тёплую заявку.\n\n"
            "Сейчас больше теряете клиентов на первом ответе или на записи?"
        )
        next_step = "Уточнить основную точку потери клиентов"
    elif str(data["niche"]) == "клиника":
        text = (
            "Для клиники AI-администратор может отвечать пациентам, уточнять запрос, "
            "помогать с записью и передавать заявку администратору. Часто пациент уходит, "
            "если не получает быстрый ответ.\n\n"
            "Бот нужен больше для первичных заявок, записи пациентов или частых вопросов?"
        )
        next_step = "Уточнить основной сценарий клиники"
    elif stage == "business_described":
        text = (
            "Понял. AI-бот может закрыть первый этап: ответить без задержки, уточнить запрос, "
            "собрать контакт и передать заявку менеджеру или в CRM.\n\n"
            "Где сейчас чаще теряются клиенты и нужна ли автоматическая запись?"
        )
        next_step = "Выявить боль и необходимость записи"
    else:
        text = (
            "Подскажу. Я занимаюсь AI-чат-ботами и AI-администраторами: они отвечают клиентам, "
            "квалифицируют заявки, помогают с записью и передают данные менеджеру или в CRM.\n\n"
            "Какая у вас ниша и где приходят заявки — Direct, Telegram или WhatsApp?"
        )
        next_step = "Уточнить нишу и канал заявок"

    return LeadReply(text, stage, str(data["lead_score"]), int(data["score"]), next_step, summary, recommended_price, is_hot)


def hot_lead_notification(message, reply: LeadReply | None = None) -> str:
    reply = reply or build_lead_reply(message.text or "")
    user = message.from_user
    username = f"@{user.username}" if getattr(user, "username", None) else "не указан"
    name = " ".join(part for part in (getattr(user, "first_name", None), getattr(user, "last_name", None)) if part) or "не указано"
    return (
        "🔥 Горячий лид\n\n"
        f"Имя: {name}\nUsername: {username}\nID: {user.id}\n"
        f"{reply.summary}\n"
        f"Lead score: {reply.lead_score} ({reply.score})\n"
        f"Следующий шаг: {reply.next_step}"
    )
