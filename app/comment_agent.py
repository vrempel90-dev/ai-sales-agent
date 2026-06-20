"""Agent that replies to incoming Threads comments and qualifies leads."""
from datetime import datetime
from sqlalchemy.orm import Session
from app.ai import generate_json, generate_text
from app.config import get_settings
from app.database import SessionLocal
from app.lead_handoff import create_or_update_lead, maybe_notify_viktor
from app.lead_scoring import calculate_lead_score, get_lead_status
from app.models import Contact, Conversation
from app.prompts import LEAD_ANALYSIS_PROMPT, REPLY_SYSTEM_PROMPT
from app.safety_guard import clean_ai_reply, should_ignore
from app.threads_api import ThreadsClient

QUALIFYING_KEYWORDS = ("сколько стоит", "цена", "хочу", "мне нужно", "можно консультацию", "для клиники", "для салона", "бот", "ai", "ии", "автоматизация", "заявки", "crm", "whatsapp", "instagram")


def generate_reply(contact: Contact, message_text: str, history: list) -> str:
    value = message_text.lower()
    if "интересно" in value and not any(word in value for word in QUALIFYING_KEYWORDS):
        return "Понял. А какой у вас бизнес? Тогда смогу точнее сказать, какой AI-агент подойдет первым."
    if "сколько стоит" in value or "цена" in value:
        return "Зависит от задачи. Простой бот и AI-агент с логикой, CRM и передачей заявок — это разные уровни. Какой у вас бизнес и что хотите автоматизировать?"
    prompt = f"Контакт: @{contact.username}. История: {history[-5:]}. Сообщение: {message_text}. Ответь коротко и задай следующий квалифицирующий вопрос: бизнес, канал заявок или что автоматизировать."
    return clean_ai_reply(generate_text(REPLY_SYSTEM_PROMPT, prompt))


async def process_reply_and_score_lead(contact: Contact, message_text: str, ai_reply: str, db: Session) -> None:
    history = [c.incoming_text for c in contact.conversations[-10:]] if contact.conversations else []
    analysis = generate_json(LEAD_ANALYSIS_PROMPT, "\n".join(history + [message_text, ai_reply]))
    score = max(int(analysis.get("lead_score") or 0), calculate_lead_score(message_text, analysis))
    analysis["lead_score"] = score
    analysis["lead_status"] = get_lead_status(score)
    contact.business_type = analysis.get("business_type") or contact.business_type
    contact.pain = analysis.get("pain") or contact.pain
    contact.lead_status = analysis["lead_status"]
    lead = create_or_update_lead(contact, analysis, db)
    await maybe_notify_viktor(lead, db)


async def handle_incoming_comment(event: dict) -> dict:
    db = SessionLocal()
    try:
        text = event.get("message_text", "")
        if should_ignore(text):
            return {"ignored": True}
        user_id = event.get("threads_user_id") or event.get("username") or "unknown"
        contact = db.query(Contact).filter(Contact.threads_user_id == str(user_id)).first()
        if contact is None:
            contact = Contact(threads_user_id=str(user_id), username=event.get("username"), source_post_id=event.get("post_id"))
            db.add(contact)
        contact.last_seen = datetime.utcnow()
        history = db.query(Conversation).filter(Conversation.contact_id == contact.id).order_by(Conversation.id.desc()).limit(10).all() if contact.id else []
        reply = generate_reply(contact, text, [h.incoming_text for h in reversed(history)])
        db.flush()
        conv = Conversation(contact_id=contact.id, incoming_text=text, response_text=reply, source_type=event.get("source_type", "comment"), threads_message_id=event.get("threads_message_id"))
        db.add(conv); db.commit(); db.refresh(contact)
        if event.get("threads_message_id"):
            await ThreadsClient().reply_to_comment(event["threads_message_id"], reply)
        await process_reply_and_score_lead(contact, text, reply, db)
        return {"ignored": False, "reply": reply}
    finally:
        db.close()
