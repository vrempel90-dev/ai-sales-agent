import asyncio

import httpx
import pytest

from app.config import Settings
from app.ollama_client import OLLAMA_ERROR, ask_ollama


def make_settings() -> Settings:
    return Settings(
        telegram_bot_token="token",
        ollama_base_url="http://ollama.test",
        ollama_model="llama-test",
        ollama_num_ctx=512,
        ollama_num_predict=300,
        ollama_num_thread=1,
        ollama_temperature=0.7,
        ollama_top_p=0.9,
        database_path=":memory:",
        threads_access_token="",
        threads_user_id="",
        threads_api_base_url="https://graph.threads.net",
        threads_auto_publish=False,
        threads_auto_posting_enabled=False,
        threads_auto_posts_per_day=3,
        threads_auto_post_hours=[10, 14, 18],
        threads_auto_post_timezone="Asia/Almaty",
        threads_auto_generate_if_queue_empty=True,
        threads_daily_post_limit=3,
    )


def test_ask_ollama_falls_back_to_generate_after_chat_500(monkeypatch):
    calls = []

    async def fake_post_ollama(client, settings, endpoint, payload):
        calls.append((endpoint, payload))
        if endpoint == "/api/chat":
            request = httpx.Request("POST", "http://ollama.test/api/chat")
            response = httpx.Response(500, text="chat exploded", request=request)
            raise httpx.HTTPStatusError("server error", request=request, response=response)
        return {"response": "fallback response"}

    monkeypatch.setattr("app.ollama_client._post_ollama", fake_post_ollama)

    result = asyncio.run(ask_ollama(make_settings(), "write post"))

    assert result == "fallback response"
    assert calls == [
        (
            "/api/chat",
            {
                "model": "llama-test",
                "messages": [{"role": "user", "content": "write post"}],
                "stream": False,
                "options": {
                    "num_ctx": 512,
                    "num_predict": 300,
                    "num_thread": 1,
                    "temperature": 0.7,
                    "top_p": 0.9,
                },
            },
        ),
        (
            "/api/generate",
            {
                "model": "llama-test",
                "prompt": "write post",
                "stream": False,
                "options": {
                    "num_ctx": 512,
                    "num_predict": 300,
                    "num_thread": 1,
                    "temperature": 0.7,
                    "top_p": 0.9,
                },
            },
        ),
    ]


def test_ask_ollama_raises_short_user_message_when_both_endpoints_fail(monkeypatch):
    async def fake_post_ollama(client, settings, endpoint, payload):
        raise httpx.TimeoutException("timed out")

    monkeypatch.setattr("app.ollama_client._post_ollama", fake_post_ollama)

    with pytest.raises(RuntimeError, match=OLLAMA_ERROR):
        asyncio.run(ask_ollama(make_settings(), "write post"))
