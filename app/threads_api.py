"""Threads / Meta Graph API wrapper.

TODO: confirm exact production endpoints and permissions in Meta Developer before live use.
"""
import logging
import httpx
from app.config import get_settings

logger = logging.getLogger(__name__)


class ThreadsClient:
    def __init__(self) -> None:
        self.settings = get_settings()
        self.base_url = self.settings.threads_api_base_url.rstrip("/")
        if not self.settings.threads_access_token:
            logger.warning("THREADS_ACCESS_TOKEN is missing; Threads calls will be skipped")

    async def publish_text_post(self, text: str) -> dict:
        if not self.settings.threads_configured:
            return {"ok": False, "skipped": True, "reason": "Threads API is not configured"}
        # TODO: replace with exact Threads media publish flow if Meta changes endpoint requirements.
        url = f"{self.base_url}/v1.0/{self.settings.threads_user_id}/threads"
        payload = {"media_type": "TEXT", "text": text, "access_token": self.settings.threads_access_token}
        try:
            async with httpx.AsyncClient(timeout=20) as client:
                response = await client.post(url, data=payload)
                response.raise_for_status()
                return response.json()
        except Exception as exc:
            logger.exception("Threads publish failed")
            return {"ok": False, "error": str(exc)}

    async def get_replies(self, post_id: str) -> list[dict]:
        if not self.settings.threads_access_token:
            return []
        url = f"{self.base_url}/v1.0/{post_id}/replies"
        try:
            async with httpx.AsyncClient(timeout=20) as client:
                response = await client.get(url, params={"access_token": self.settings.threads_access_token})
                response.raise_for_status()
                return response.json().get("data", [])
        except Exception:
            logger.exception("Threads get replies failed")
            return []

    async def reply_to_comment(self, comment_id: str, text: str) -> dict:
        if not self.settings.threads_access_token:
            return {"ok": False, "skipped": True}
        # TODO: verify comment reply endpoint and permissions in Meta Developer.
        url = f"{self.base_url}/v1.0/{comment_id}/replies"
        try:
            async with httpx.AsyncClient(timeout=20) as client:
                response = await client.post(url, data={"text": text, "access_token": self.settings.threads_access_token})
                response.raise_for_status()
                return response.json()
        except Exception as exc:
            logger.exception("Threads reply failed")
            return {"ok": False, "error": str(exc)}

    def verify_webhook_token(self, token: str) -> bool:
        expected = self.settings.threads_webhook_verify_token
        return bool(expected and token == expected)

    def parse_webhook_event(self, payload: dict) -> list[dict]:
        events: list[dict] = []
        for entry in payload.get("entry", []):
            for change in entry.get("changes", []):
                value = change.get("value", {})
                events.append({
                    "source_type": value.get("type") or change.get("field") or "comment",
                    "message_text": value.get("text") or value.get("message") or "",
                    "threads_user_id": str(value.get("from", {}).get("id") or value.get("user_id") or "unknown"),
                    "username": value.get("from", {}).get("username") or value.get("username"),
                    "threads_message_id": str(value.get("id") or value.get("comment_id") or ""),
                    "post_id": str(value.get("post_id") or value.get("media_id") or ""),
                    "source_url": value.get("permalink") or "",
                })
        return events
