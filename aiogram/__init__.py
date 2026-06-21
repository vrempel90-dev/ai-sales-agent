"""Small aiogram-compatible subset used by the app in lightweight deployments/tests."""
import asyncio
import dataclasses
import logging

import httpx

logger = logging.getLogger("aiogram")


def serialize_telegram_payload(value):
    """Convert local aiogram-like objects into JSON-safe Telegram API payloads."""
    if value is None:
        return None
    if hasattr(value, "model_dump"):
        return value.model_dump(exclude_none=True)
    if hasattr(value, "dict"):
        return value.dict(exclude_none=True)
    if dataclasses.is_dataclass(value):
        return dataclasses.asdict(value)
    if isinstance(value, list):
        return [serialize_telegram_payload(item) for item in value]
    if isinstance(value, tuple):
        return [serialize_telegram_payload(item) for item in value]
    if isinstance(value, dict):
        return {
            key: serialize_telegram_payload(item)
            for key, item in value.items()
            if item is not None
        }
    return value


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
        payload = {"chat_id": chat_id, "text": text, **kwargs}
        try:
            return await self._request("sendMessage", payload)
        except TypeError:
            if "reply_markup" not in payload:
                raise
            logger.exception("Telegram sendMessage payload serialization failed; retrying without reply_markup")
            payload.pop("reply_markup", None)
            return await self._request("sendMessage", payload)
    async def delete_webhook(self, **kwargs):
        return await self._request("deleteWebhook", kwargs)
    async def close(self):
        await self._client.aclose()
    async def _request(self, method: str, payload: dict):
        payload = serialize_telegram_payload(payload)
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
            except httpx.HTTPStatusError as exc:
                if exc.response.status_code == 409:
                    logger.warning("Telegram polling conflict (409); another poller may still be shutting down. Retrying after pause.")
                else:
                    logger.exception("Telegram polling HTTP iteration failed")
                await asyncio.sleep(5)
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
