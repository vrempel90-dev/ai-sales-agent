from dataclasses import dataclass
import re


STAGES = {
    "new_interest",
    "price_question",
    "business_described",
    "audit_agreed",
    "hot_lead",
    "irrelevant_site_request",
    "negative",
}

INTEREST_MARKERS = (
    "интересно", "расскажите", "хочу бота", "можно подробнее",
    "что вы делаете", "как работает", "бот для бизнеса",
)
PRICE_MARKERS = ("цена", "стоимость", "сколько стоит", "прайс")
SITE_MARKERS = (
    "сайт", "лендинг", "web-прилож", "веб-прилож", "html", "css", "javascript",
)
HOT_MARKERS = (
    "хочу заказать", "давайте делать", "когда начнём", "когда начнем",
    "давайте созвон", "нужен бот", "готов обсудить", "как оплатить",
    "можем созвониться",
)
AUDIT_MARKERS = (
    "согласен на аудит", "давайте аудит", "хочу аудит", "проведите аудит",
    "да, давайте", "готов к аудиту",
)
NEGATIVE_MARKERS = (
    "не интересно", "неинтересно", "отстаньте", "не пишите", "спам",
    "ерунда", "бред", "идиот",
)
BUSINESS_MARKERS = (
    "у нас", "мой бизнес", "занимаюсь", "ниша", "салон", "клиник",
    "магазин", "школ", "ресторан", "услуг", "заявки", "direct", "директ",
    "telegram", "телеграм", "whatsapp", "ватсап", "crm", "црм",
)


@dataclass(frozen=True)
class LeadReply:
    text: str
    stage: str
    is_hot: bool = False


def _contains(text: str, markers: tuple[str, ...]) -> bool:
    return any(marker in text for marker in markers)


def contact_destination(contact_link: str, phone: str) -> str | None:
    if contact_link.strip():
        return contact_link.strip()
    if phone.strip():
        return phone.strip()
    return None


def classify_stage(message: str) -> str:
    text = " ".join((message or "").lower().split())
    if _contains(text, SITE_MARKERS):
        return "irrelevant_site_request"
    if _contains(text, HOT_MARKERS):
        return "hot_lead"
    if _contains(text, NEGATIVE_MARKERS):
        return "negative"
    if _contains(text, PRICE_MARKERS):
        return "price_question"
    if _contains(text, AUDIT_MARKERS):
        return "audit_agreed"
    if _contains(text, BUSINESS_MARKERS):
        return "business_described"
    return "new_interest"


def build_lead_reply(message: str, contact_link: str = "", phone: str = "") -> LeadReply:
    stage = classify_stage(message)

    if stage == "irrelevant_site_request":
        return LeadReply(
            "Сайты не делаю. Я специализируюсь именно на AI-чат-ботах и автоматизации "
            "обработки заявок. Могу помочь сделать бота, который принимает заявки из "
            "Direct, Telegram или WhatsApp, отвечает клиентам и передаёт данные вам или в CRM.",
            stage,
        )
    if stage == "hot_lead":
        destination = contact_destination(contact_link, phone)
        if destination:
            text = (
                "Отлично, давайте тогда перейдём в WhatsApp — там быстрее обсудим детали "
                "и я задам пару вопросов по процессу.\n\n"
                f"Вот WhatsApp: {destination}"
            )
        else:
            text = (
                "Отлично, давайте обсудим детали. Оставьте, пожалуйста, номер телефона "
                "или удобный способ связи — я напишу вам."
            )
        return LeadReply(text, stage, is_hot=True)
    if stage == "negative":
        return LeadReply(
            "Понимаю. Я не навязываю. Если у вас есть поток заявок и часть общения идёт "
            "вручную, могу просто подсказать, где там можно убрать рутину с помощью AI-бота.",
            stage,
        )
    if stage == "price_question":
        return LeadReply(
            "Цена зависит от задачи. Одно дело — простой бот для ответов и сбора заявок, "
            "другое — AI-администратор с записью, услугами, прайсом и передачей в CRM.\n\n"
            "Сначала лучше понять ваш процесс, чтобы не предлагать лишнее. "
            "Какая у вас ниша и где сейчас приходят заявки?",
            stage,
        )
    if stage == "audit_agreed":
        return LeadReply(
            "Отлично. Тогда для мини-аудита ответьте коротко:\n\n"
            "1. Какие услуги продаёте?\n"
            "2. Где приходят заявки?\n"
            "3. Кто сейчас отвечает клиентам?\n"
            "4. Какие вопросы задают чаще всего?\n"
            "5. Нужно просто собирать заявки или ещё записывать клиентов на время?",
            stage,
        )
    if stage == "business_described":
        business = re.sub(r"\s+", " ", message).strip()
        summary = business[:180] + ("…" if len(business) > 180 else "")
        return LeadReply(
            f"Понял: {summary}\n\n"
            "В такой схеме часть обращений может теряться из-за долгого ответа или ручной "
            "обработки. AI-бот может закрыть первый этап: ответить на частые вопросы, "
            "уточнить запрос, собрать контакт и передать заявку вам или в CRM.\n\n"
            "Что сейчас отнимает больше времени: ответы на вопросы или запись клиентов?",
            stage,
        )
    return LeadReply(
        "Да, подскажу. Я занимаюсь AI-чат-ботами для бизнеса: они отвечают клиентам, "
        "собирают заявки, помогают с записью и передают данные менеджеру или в CRM.\n\n"
        "Какая у вас ниша и где сейчас приходят заявки — Direct, Telegram или WhatsApp?",
        "new_interest",
    )


def hot_lead_notification(message) -> str:
    user = message.from_user
    username = f"@{user.username}" if getattr(user, "username", None) else "не указан"
    name = " ".join(
        part for part in (getattr(user, "first_name", None), getattr(user, "last_name", None))
        if part
    ) or "не указано"
    return (
        "🔥 Горячий лид\n"
        f"Имя: {name}\n"
        f"Username: {username}\n"
        f"ID: {user.id}\n"
        f"Сообщение: {message.text or ''}\n"
        "Стадия: хочет обсудить / созвон / заказать\n"
        "Рекомендуемое действие: написать в WhatsApp или продолжить диалог."
    )
