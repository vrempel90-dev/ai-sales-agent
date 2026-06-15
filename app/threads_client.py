import httpx
from .config import Settings

THREADS_NOT_CONFIGURED = "Threads API пока не настроен. Добавьте THREADS_ACCESS_TOKEN и THREADS_USER_ID в .env. До этого я могу только готовить посты и держать их в очереди."

class ThreadsClient:
    def __init__(self, settings: Settings): self.settings = settings
    def _ensure_configured(self):
        if not self.settings.threads_access_token or not self.settings.threads_user_id:
            raise RuntimeError(THREADS_NOT_CONFIGURED)
    async def create_text_container(self, text: str) -> str:
        self._ensure_configured()
        url = f"{self.settings.threads_api_base_url.rstrip('/')}/{self.settings.threads_user_id}/threads"
        data = {"media_type": "TEXT", "text": text, "access_token": self.settings.threads_access_token}
        async with httpx.AsyncClient(timeout=30) as client:
            r = await client.post(url, data=data)
        if r.is_error: raise RuntimeError(f"Ошибка Threads API при создании контейнера: {r.text}")
        cid = r.json().get("id")
        if not cid: raise RuntimeError("Threads API не вернул id контейнера.")
        return cid
    async def publish_container(self, container_id: str) -> dict:
        self._ensure_configured()
        url = f"{self.settings.threads_api_base_url.rstrip('/')}/{self.settings.threads_user_id}/threads_publish"
        data = {"creation_id": container_id, "access_token": self.settings.threads_access_token}
        async with httpx.AsyncClient(timeout=30) as client:
            r = await client.post(url, data=data)
        if r.is_error: raise RuntimeError(f"Ошибка Threads API при публикации: {r.text}")
        return r.json()
    async def publish_text_post(self, text: str) -> dict:
        cid = await self.create_text_container(text)
        return await self.publish_container(cid)
