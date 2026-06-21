import asyncio

import pytest

from aiogram import Bot, serialize_telegram_payload
from aiogram.types import Chat, InlineKeyboardButton, InlineKeyboardMarkup, Message
from app.handlers.agents import show_post
from app.post_queue import QueuedPost


class FakeClient:
    def __init__(self, *, raise_on_keyboard=False):
        self.payloads = []
        self.raise_on_keyboard = raise_on_keyboard

    async def post(self, url, json):
        self.payloads.append(json)
        if self.raise_on_keyboard and "reply_markup" in json:
            raise TypeError("Object of type InlineKeyboardMarkup is not JSON serializable")
        return FakeResponse()


class FakeResponse:
    def raise_for_status(self):
        return None

    def json(self):
        return {"ok": True, "result": {"message_id": 1}}


@pytest.mark.parametrize(
    ("button", "expected"),
    [
        (InlineKeyboardButton(text="Next", callback_data="threads:next"), {"text": "Next", "callback_data": "threads:next"}),
        (InlineKeyboardButton(text="Open", url="https://example.com"), {"text": "Open", "url": "https://example.com"}),
    ],
)
def test_inline_keyboard_button_serializes_callback_data_and_url_without_none(button, expected):
    assert button.model_dump() == expected


def test_serialize_telegram_payload_converts_inline_keyboard_markup_to_json_dict():
    markup = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Publish", callback_data="threads:publish:1")],
            [InlineKeyboardButton(text="Docs", url="https://example.com")],
        ]
    )

    assert serialize_telegram_payload({"reply_markup": markup, "none": None}) == {
        "reply_markup": {
            "inline_keyboard": [
                [{"text": "Publish", "callback_data": "threads:publish:1"}],
                [{"text": "Docs", "url": "https://example.com"}],
            ]
        }
    }


def test_send_message_serializes_reply_markup_and_does_not_raise_type_error():
    bot = Bot("token")
    bot._client = FakeClient()
    markup = InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="Next", callback_data="threads:next")]]
    )

    asyncio.run(bot.send_message(123, "post", reply_markup=markup))

    assert bot._client.payloads == [
        {
            "chat_id": 123,
            "text": "post",
            "reply_markup": {
                "inline_keyboard": [[{"text": "Next", "callback_data": "threads:next"}]]
            },
        }
    ]


def test_plain_send_message_without_reply_markup_still_works():
    bot = Bot("token")
    bot._client = FakeClient()

    asyncio.run(bot.send_message(123, "plain"))

    assert bot._client.payloads == [{"chat_id": 123, "text": "plain"}]


def test_send_message_falls_back_without_keyboard_if_serialization_still_fails():
    bot = Bot("token")
    bot._client = FakeClient(raise_on_keyboard=True)
    markup = InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="Next", callback_data="threads:next")]]
    )

    asyncio.run(bot.send_message(123, "post", reply_markup=markup))

    assert len(bot._client.payloads) == 2
    assert "reply_markup" in bot._client.payloads[0]
    assert bot._client.payloads[1] == {"chat_id": 123, "text": "post"}


def test_offer_post_can_render_post_with_keyboard():
    bot = Bot("token")
    bot._client = FakeClient()
    message = Message(chat=Chat(id=123), bot=bot)
    post = QueuedPost(id="42", text="Тестовый пост", status="draft", created_at="2026-06-21T00:00:00+00:00")

    asyncio.run(show_post(message, post))

    payload = bot._client.payloads[0]
    assert payload["reply_markup"]["inline_keyboard"][0][0] == {
        "text": "✅ Опубликовать",
        "callback_data": "threads:publish:42",
    }


def test_threads_next_can_render_post_with_keyboard():
    bot = Bot("token")
    bot._client = FakeClient()
    message = Message(chat=Chat(id=123), bot=bot)
    post = QueuedPost(id="43", text="Следующий тестовый пост", status="draft", created_at="2026-06-21T00:00:00+00:00")

    asyncio.run(show_post(message, post))

    payload = bot._client.payloads[0]
    assert payload["reply_markup"]["inline_keyboard"][1][1] == {
        "text": "➡️ Следующий",
        "callback_data": "threads:next",
    }
