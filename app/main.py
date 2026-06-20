"""FastAPI entrypoint for the autonomous Threads AI sales agent."""
import logging
from datetime import datetime
from contextlib import asynccontextmanager
from fastapi import Depends, FastAPI, HTTPException, Query, Request
from fastapi.responses import PlainTextResponse
from sqlalchemy.orm import Session
from app.comment_agent import handle_incoming_comment
from app.config import get_settings
from app.content_agent import choose_topic, generate_post, save_generated_post
from app.database import get_db, init_db
from app.models import Lead, Post
from app.schemas import GeneratePostRequest, LeadResponse, PostResponse, PublishPostRequest
from app.scheduler import start_scheduler
from app.threads_api import ThreadsClient

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    settings.log_startup()
    init_db()
    start_scheduler()
    yield

app = FastAPI(title="AI Sales Agent for Threads", version="1.0.0", lifespan=lifespan)

@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}

@app.get("/webhooks/threads")
def verify_threads_webhook(
    hub_mode: str | None = Query(default=None, alias="hub.mode"),
    hub_verify_token: str | None = Query(default=None, alias="hub.verify_token"),
    hub_challenge: str | None = Query(default=None, alias="hub.challenge"),
):
    if hub_mode == "subscribe" and hub_challenge and ThreadsClient().verify_webhook_token(hub_verify_token or ""):
        return PlainTextResponse(hub_challenge)
    raise HTTPException(status_code=403, detail="Invalid verify token")

@app.post("/webhooks/threads")
async def threads_webhook(request: Request) -> dict:
    payload = await request.json()
    events = ThreadsClient().parse_webhook_event(payload)
    results = [await handle_incoming_comment(event) for event in events]
    return {"processed": len(results), "results": results}

@app.post("/admin/generate-post", response_model=PostResponse | dict)
def admin_generate_post(request: GeneratePostRequest, db: Session = Depends(get_db)):
    topic = request.topic or choose_topic()
    text = generate_post(topic)
    if not request.save:
        return {"text": text, "topic": topic, "status": "not_saved"}
    return save_generated_post(text, topic, db)

@app.post("/admin/publish-post", response_model=PostResponse)
async def admin_publish_post(request: PublishPostRequest, db: Session = Depends(get_db)):
    post = db.get(Post, request.post_id) if request.post_id else None
    if post is None:
        if not request.text:
            topic = request.topic or choose_topic()
            text = generate_post(topic)
        else:
            topic = request.topic
            text = request.text
        post = save_generated_post(text, topic or "manual", db)
    result = await ThreadsClient().publish_text_post(post.text)
    post.status = "published" if result.get("id") or result.get("ok") else "failed"
    post.threads_post_id = str(result.get("id") or result.get("post_id") or "") or None
    post.published_at = datetime.utcnow() if post.status == "published" else None
    db.commit(); db.refresh(post)
    return post

@app.get("/admin/leads", response_model=list[LeadResponse])
def admin_leads(db: Session = Depends(get_db)):
    return db.query(Lead).order_by(Lead.created_at.desc()).limit(100).all()

@app.get("/admin/posts", response_model=list[PostResponse])
def admin_posts(db: Session = Depends(get_db)):
    return db.query(Post).order_by(Post.created_at.desc()).limit(100).all()
