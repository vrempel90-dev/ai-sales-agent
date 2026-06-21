"""Small aiogram-compatible subset used by the app in lightweight deployments/tests."""
import asyncio
import logging

import httpx

logger = logging.getLogger("aiogram")

class _FExpr:
    def startswith(self, *_args, **_kwargs): return self
    def __invert__(self): return self
    def __and__(self, _other): return self
    def __rand__(self, _other): return self
    def __eq__(self, _other): return self

class _F:
    def __getattr__(self, _name): return _FExpr()
F = _F()

class Router:
    def __init__(self):
        self.message_handlers = []
        self.callback_handlers = []
    def message(self, *filters, **_kwargs):
        def decorator(func):
            self.message_handlers.append((filters, func))
            return func
        return decorator
    def callback_query(self, *filters, **_kwargs):
        def decorator(func):
            self.callback_handlers.append((filters, func))
            return func
        return decorator

class Bot:
    def __init__(self, token: str):
        self.token = token
        self.base_url = f"https://api.telegram.org/bot{token}"
        self._client = httpx.AsyncClient(timeout=35.0)
    async def send_message(self, chat_id, text: str, **kwargs):
        return await self._request("sendMessage", {"chat_id": chat_id, "text": text, **kwargs})
    async def delete_webhook(self, **kwargs):
        return await self._request("deleteWebhook", kwargs)
    async def close(self):
        await self._client.aclose()
    async def _request(self, method: str, payload: dict):
        response = await self._client.post(f"{self.base_url}/{method}", json=payload)
        response.raise_for_status()
        return response.json()

class Dispatcher:
    def __init__(self, **data):
        self.routers = []
        self.data = data
    def include_router(self, router: Router):
        self.routers.append(router)
    async def start_polling(self, bot: Bot, **_kwargs):
        logger.info("Start polling")
        offset = None
        while True:
            params = {"timeout": 30}
            if offset is not None:
                params["offset"] = offset
            try:
                response = await bot._client.get(f"{bot.base_url}/getUpdates", params=params)
                response.raise_for_status()
                updates = response.json().get("result", [])
                for update in updates:
                    offset = update.get("update_id", 0) + 1
                    message = update.get("message") or update.get("edited_message")
                    if message:
                        await self._dispatch_message(bot, message)
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("Telegram polling iteration failed")
                await asyncio.sleep(5)
    async def _dispatch_message(self, bot: Bot, payload: dict):
        from aiogram.filters import Command, CommandStart
        from aiogram.types import Message
        message = Message.from_payload(payload, bot)
        text = message.text or ""
        for router in self.routers:
            for filters, handler in router.message_handlers:
                if not _matches(filters, text, Command, CommandStart):
                    continue
                kwargs = _build_kwargs(handler, message, self.data)
                await handler(**kwargs)
                return

def _matches(filters, text, Command, CommandStart):
    if not filters:
        return True
    for flt in filters:
        if isinstance(flt, CommandStart):
            return text.split(maxsplit=1)[0] == "/start"
        if isinstance(flt, Command):
            command = text.split(maxsplit=1)[0].removeprefix("/").split("@", 1)[0]
            return command in flt.commands
    return not text.startswith("/")

def _build_kwargs(handler, message, data):
    import inspect
    kwargs = {}
    for name in inspect.signature(handler).parameters:
        if name in {"message", "message_or_cb"}:
            kwargs[name] = message
        elif name in data:
            kwargs[name] = data[name]
    return kwargs
