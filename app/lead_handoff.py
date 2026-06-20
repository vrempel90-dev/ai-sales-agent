"""Create/update leads and notify Viktor only for hot leads."""
from sqlalchemy.orm import Session
from app.config import get_settings
from app.lead_scoring import should_notify
from app.models import Contact, Lead
from app.telegram_notify import send_hot_lead


def create_or_update_lead(contact: Contact, analysis: dict, db: Session) -> Lead:
    lead = db.query(Lead).filter(Lead.contact_id == contact.id).order_by(Lead.id.desc()).first()
    if lead is None:
        lead = Lead(contact_id=contact.id, username=contact.username)
        db.add(lead)
    lead.username = contact.username
    lead.business_type = analysis.get("business_type") or contact.business_type
    lead.channel = analysis.get("channel")
    lead.pain = analysis.get("pain") or contact.pain
    lead.desired_solution = analysis.get("desired_solution")
    lead.lead_score = int(analysis.get("lead_score") or 0)
    lead.summary = analysis.get("summary")
    lead.recommended_next_step = analysis.get("recommended_next_step")
    lead.source_url = analysis.get("source_url")
    if lead.lead_score >= get_settings().lead_score_threshold:
        lead.status = "new"
    db.commit(); db.refresh(lead)
    return lead


async def maybe_notify_viktor(lead: Lead, db: Session) -> bool:
    settings = get_settings()
    if lead.sent_to_viktor or not should_notify(lead.lead_score, settings.lead_score_threshold):
        return False
    if await send_hot_lead(lead):
        lead.sent_to_viktor = True
        lead.status = "sent"
        db.commit()
        return True
    return False
