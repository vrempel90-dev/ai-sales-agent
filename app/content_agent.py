"""Content generation agent for Threads."""
import random
from sqlalchemy.orm import Session
from app.ai import generate_text
from app.database import SessionLocal
from app.models import Post
from app.prompts import CONTENT_SYSTEM_PROMPT

TOPICS = ["почему бизнес теряет заявки", "AI-админ для клиник", "AI-продавец для услуг", "автоматизация записи", "обработка заявок ночью", "отличие AI-агента от обычного бота", "CRM и заявки", "как AI помогает админам", "ошибки бизнеса в переписках", "почему скорость ответа влияет на продажи", "как бизнес теряет клиентов в Instagram/WhatsApp"]


def choose_topic() -> str:
    return random.choice(TOPICS)


def generate_post(topic: str | None = None) -> str:
    topic = topic or choose_topic()
    prompt = f"Напиши короткий Threads-пост на тему: {topic}. Заверши мягким вопросом для комментариев."
    return generate_text(CONTENT_SYSTEM_PROMPT, prompt)


def generate_daily_posts(count: int) -> list[str]:
    return [generate_post() for _ in range(max(0, count))]


def save_generated_post(text: str, topic: str, db: Session | None = None) -> Post:
    own = db is None
    db = db or SessionLocal()
    try:
        post = Post(text=text, topic=topic, status="draft")
        db.add(post)
        db.commit()
        db.refresh(post)
        return post
    finally:
        if own:
            db.close()
