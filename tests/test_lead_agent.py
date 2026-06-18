import asyncio
from types import SimpleNamespace

from app.handlers.sales import lead_mode_on, owner_access_error
from app.lead_agent import build_lead_reply


def test_interest_asks_qualification_questions():
    reply = build_lead_reply("Интересно, расскажите подробнее")
    assert reply.stage == "new_interest"
    assert "Какая у вас ниша" in reply.text
    assert "Direct, Telegram или WhatsApp" in reply.text


def test_price_question_does_not_name_price():
    reply = build_lead_reply("Сколько стоит бот?")
    assert reply.stage == "price_question"
    assert "Цена зависит от задачи" in reply.text
    assert not any(amount in reply.text for amount in ("50 000", "100 000", "₸", "$"))


def test_salon_dm_reply_uses_sales_strategy_and_qualification():
    reply = build_lead_reply("Хочу AI-бота для салона")
    assert reply.stage == "business_described"
    assert "для салона это как раз сильный кейс" in reply.text
    assert "админ долго отвечает" in reply.text
    assert "AI-бот закрывает первый этап" in reply.text
    assert "первом ответе или на записи клиентов?" in reply.text
    assert not any(amount in reply.text for amount in ("₸", "$", "50 000"))


def test_site_request_returns_focus_to_ai_bots():
    reply = build_lead_reply("Вы можете сделать сайт или лендинг?")
    assert reply.stage == "irrelevant_site_request"
    assert reply.text.startswith("Сайты не делаю.")
    assert "AI-чат-ботах" in reply.text


def test_hot_lead_gets_whatsapp_link():
    reply = build_lead_reply(
        "Давайте делать, хочу заказать",
        "https://wa.me/77712841932",
        "+77712841932",
    )
    assert reply.stage == "hot_lead"
    assert reply.is_hot is True
    assert "https://wa.me/77712841932" in reply.text
    assert "+77712841932" not in reply.text


def test_hot_lead_uses_phone_when_link_is_missing():
    reply = build_lead_reply("Нужен бот", "", "+77712841932")
    assert "+77712841932" in reply.text


def test_lead_mode_commands_reject_non_owner():
    settings = SimpleNamespace(owner_telegram_id=100)
    message = SimpleNamespace(from_user=SimpleNamespace(id=200))
    assert owner_access_error(message, settings) == "Эта команда доступна только владельцу."


def test_lead_mode_commands_reject_when_owner_is_not_configured():
    settings = SimpleNamespace(owner_telegram_id=None)
    message = SimpleNamespace(from_user=SimpleNamespace(id=200))
    assert owner_access_error(message, settings) == "OWNER_TELEGRAM_ID не настроен."


def test_lead_mode_on_does_not_change_state_for_non_owner():
    answers = []

    async def answer(text):
        answers.append(text)

    message = SimpleNamespace(from_user=SimpleNamespace(id=200), answer=answer)
    settings = SimpleNamespace(owner_telegram_id=100)
    service = SimpleNamespace(enabled=False)
    asyncio.run(lead_mode_on(message, settings, service))
    assert service.enabled is False
    assert answers == ["Эта команда доступна только владельцу."]
