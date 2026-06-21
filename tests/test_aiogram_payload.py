import asyncio

import httpx
import pytest

from aiogram import Bot, Dispatcher
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


def test_inline_keyboard_button_model_dump_returns_json_safe_dict():
    button = InlineKeyboardButton(text="Open", callback_data="threads:next", url=None)

    assert button.model_dump() == {"text": "Open", "callback_data": "threads:next"}


def test_inline_keyboard_markup_model_dump_returns_json_safe_dict():
    markup = InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="Next", callback_data="threads:next")]]
    )

    assert markup.model_dump() == {
        "inline_keyboard": [[{"text": "Next", "callback_data": "threads:next"}]]
    }


class RecordingClient:
    def __init__(self):
        self.payloads = []

    async def post(self, _url, json):
        self.payloads.append(json)
        return httpx.Response(200, request=httpx.Request("POST", _url), json={"ok": True})

    async def aclose(self):
        pass


def test_bot_request_serializes_reply_markup_before_httpx_json():
    bot = Bot("token")
    client = RecordingClient()
    bot._client = client
    markup = InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="Publish", callback_data="threads:publish:1")]]
    )

    asyncio.run(bot._request("sendMessage", {"chat_id": 1, "text": "post", "reply_markup": markup}))

    assert client.payloads == [
        {
            "chat_id": 1,
            "text": "post",
            "reply_markup": {
                "inline_keyboard": [[{"text": "Publish", "callback_data": "threads:publish:1"}]]
            },
        }
    ]


def test_send_message_with_reply_markup_does_not_raise_type_error():
    bot = Bot("token")
    client = RecordingClient()
    bot._client = client
    markup = InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="Next", callback_data="threads:next")]]
    )

    asyncio.run(bot.send_message(1, "post", reply_markup=markup))

    assert client.payloads[0]["reply_markup"] == {
        "inline_keyboard": [[{"text": "Next", "callback_data": "threads:next"}]]
    }


def test_plain_send_message_without_reply_markup_still_works():
    bot = Bot("token")
    client = RecordingClient()
    bot._client = client

    asyncio.run(bot.send_message(1, "plain"))

    assert client.payloads == [{"chat_id": 1, "text": "plain"}]


class FailingMarkup:
    def model_dump(self, exclude_none=True):
        raise TypeError("cannot serialize keyboard")


def test_send_message_fallback_retries_without_keyboard_if_serialization_fails():
    bot = Bot("token")
    client = RecordingClient()
    bot._client = client

    asyncio.run(bot.send_message(1, "post", reply_markup=FailingMarkup()))

    assert client.payloads == [{"chat_id": 1, "text": "post"}]


class ConflictThenCancelledClient:
    def __init__(self):
        self.calls = 0

    async def get(self, _url, params):
        self.calls += 1
        if self.calls == 1:
            request = httpx.Request("GET", "https://api.telegram.org/bottoken/getUpdates")
            return httpx.Response(409, request=request, json={"ok": False})
        raise asyncio.CancelledError


def test_polling_409_conflict_is_warning_and_retried(monkeypatch, caplog):
    async def fast_sleep(_seconds):
        return None

    bot = Bot("token")
    client = ConflictThenCancelledClient()
    bot._client = client
    dispatcher = Dispatcher()
    monkeypatch.setattr("aiogram.asyncio.sleep", fast_sleep)

    with pytest.raises(asyncio.CancelledError):
        asyncio.run(dispatcher.start_polling(bot))

    assert client.calls == 2
    assert "polling conflict (409)" in caplog.text
