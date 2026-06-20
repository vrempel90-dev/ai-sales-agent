"""Pydantic API schemas."""
from datetime import datetime
from pydantic import BaseModel, ConfigDict

class PostCreate(BaseModel):
    text: str
    topic: str | None = None

class PostResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    threads_post_id: str | None = None
    text: str
    topic: str | None = None
    status: str
    published_at: datetime | None = None
    comments_count: int
    leads_count: int
    created_at: datetime

class LeadResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    username: str | None = None
    business_type: str | None = None
    channel: str | None = None
    pain: str | None = None
    desired_solution: str | None = None
    lead_score: int
    status: str
    summary: str | None = None
    source_url: str | None = None
    sent_to_viktor: bool
    created_at: datetime

class GeneratePostRequest(BaseModel):
    topic: str | None = None
    save: bool = True

class PublishPostRequest(BaseModel):
    post_id: int | None = None
    text: str | None = None
    topic: str | None = None

class WebhookEvent(BaseModel):
    source_type: str = "comment"
    message_text: str
    threads_user_id: str
    username: str | None = None
    threads_message_id: str | None = None
    post_id: str | None = None
    source_url: str | None = None
