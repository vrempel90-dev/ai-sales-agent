import httpx
from .config import Settings

OLLAMA_ERROR = "Ollama не отвечает. Проверьте, что она запущена и модель скачана."

async def ask_ollama(settings: Settings, prompt: str) -> str:
    try:
        async with httpx.AsyncClient(timeout=90) as client:
            r = await client.post(f"{settings.ollama_base_url.rstrip('/')}/api/generate", json={"model": settings.ollama_model, "prompt": prompt, "stream": False})
            r.raise_for_status()
            return r.json().get("response", "").strip() or "Не получилось получить ответ от модели."
    except httpx.HTTPError as exc:
        raise RuntimeError(OLLAMA_ERROR) from exc
