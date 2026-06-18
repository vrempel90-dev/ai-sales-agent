import asyncio
from types import SimpleNamespace

from app.handlers.sales import lead_mode_on, owner_access_error, sales_preview, sales_status
from app.lead_agent import build_lead_reply, hot_lead_notification
from app.lead_store import LeadConversationService


def test_interest_asks_qualification_questions():
    reply = build_lead_reply("Интересно, расскажите подробнее")
    assert reply.lead_score == "cold"
    assert "Какая у вас ниша" in reply.text
    assert "Direct, Telegram или WhatsApp" in reply.text


def test_price_question_gives_safe_range_and_asks_question():
    reply = build_lead_reply("Сколько стоит бот?")
    assert reply.stage == "price_question"
    assert reply.lead_score == "warm"
    assert "от 150 000 ₸" in reply.text
    assert "Для какой ниши" in reply.text
    assert "точную стоимость" in reply.text
    assert "30 000 ₸" not in reply.text
    assert "точно сделаю за" not in reply.text.lower()


def test_salon_dm_reply_uses_sales_strategy_and_qualification():
    reply = build_lead_reply("Хочу AI-бота для салона")
    assert reply.lead_score == "hot"
    assert "Для салона это сильный кейс" in reply.text
    assert "AI-бот отвечает сразу" in reply.text
    assert "помогает с записью" in reply.text
    assert "Оставьте номер или удобный контакт" in reply.text


def test_clinic_reply_explains_value_and_qualifies():
    reply = build_lead_reply("Мне нужен помощник для клиники")
    assert "AI-администратор" in reply.text
    assert "записи пациентов или частых вопросов?" in reply.text


def test_site_request_returns_focus_to_ai_bots():
    reply = build_lead_reply("Вы можете сделать сайт или лендинг?")
    assert reply.stage == "irrelevant_site_request"
    assert reply.text.startswith("Сайты не делаю.")
    assert "AI-чат-ботах" in reply.text


def test_hot_lead_gets_whatsapp_link_and_summary():
    reply = build_lead_reply(
        "У нас салон, заявки теряются в Direct. Давайте делать бота",
        "https://wa.me/77712841932",
        "+77712841932",
    )
    assert reply.stage == "hot_lead"
    assert reply.lead_score == "hot"
    assert reply.is_hot is True
    assert "https://wa.me/77712841932" in reply.text
    assert "+77712841932" not in reply.text
    assert "Ниша: салон красоты" in reply.summary
    assert "Канал: Instagram/Direct" in reply.summary


def test_owner_notification_contains_sales_summary():
    message = SimpleNamespace(
        text="У нас салон, долго отвечаем в Direct, давайте делать бота",
        from_user=SimpleNamespace(id=7, username="lead", first_name="Анна", last_name=None),
    )
    reply = build_lead_reply(message.text, "https://wa.me/7")
    notification = hot_lead_notification(message, reply)
    assert "🔥 Горячий лид" in notification
    assert "Ниша: салон красоты" in notification
    assert "Боль: описана реальная проблема" in notification
    assert "Рекомендуемый чек:" in notification
    assert "Следующий шаг: Написать клиенту в WhatsApp" in notification


def test_payment_is_handed_to_owner_without_accepting_money():
    reply = build_lead_reply("Хочу оплатить, куда переводить?", "https://wa.me/7")
    assert reply.is_hot is True
    assert "передам вас владельцу" in reply.text
    assert "финальное подтверждение" in reply.text
    assert "оплатите" not in reply.text.lower()


def test_agent_does_not_promise_guaranteed_result_or_exact_price():
    samples = [
        build_lead_reply("Сколько стоит бот?").text,
        build_lead_reply("Хочу AI-бота для салона").text,
        build_lead_reply("Нужно сделать бота, заявки теряются", "https://wa.me/7").text,
    ]
    combined = " ".join(samples).lower()
    assert "100%" not in combined
    assert "гарантир" not in combined
    assert "точно сделаю за" not in combined
    assert "оплата сейчас" not in combined


def test_lead_store_saves_and_returns_summary(tmp_path):
    service = LeadConversationService(str(tmp_path / "leads.db"), True)
    user = SimpleNamespace(id=1, username="lead", first_name="A", last_name=None)
    service.store.record(user, "Нужен бот", "hot_lead", "hot", "Ниша: салон")
    assert service.store.last_summary() == "Ниша: салон"


def _owner_message(text):
    answers = []

    async def answer(value):
        answers.append(value)

    return SimpleNamespace(
        text=text,
        from_user=SimpleNamespace(id=100, username="owner", first_name="Owner", last_name=None),
        answer=answer,
    ), answers


def test_sales_status_works(tmp_path):
    message, answers = _owner_message("/sales_status")
    settings = SimpleNamespace(owner_telegram_id=100, whatsapp_contact_link="https://wa.me/7", whatsapp_phone="")
    service = LeadConversationService(str(tmp_path / "status.db"), True)
    asyncio.run(sales_status(message, settings, service))
    assert "AI Sales Closing Agent enabled: yes" in answers[0]
    assert "Price ranges loaded: 5" in answers[0]
    assert "Hot lead threshold: 5" in answers[0]


def test_sales_preview_shows_score_next_step_and_notification():
    message, answers = _owner_message("/sales_preview У нас салон, заявки теряются в Direct, давайте делать бота")
    settings = SimpleNamespace(owner_telegram_id=100, whatsapp_contact_link="https://wa.me/7", whatsapp_phone="")
    asyncio.run(sales_preview(message, settings))
    assert "Lead score: hot" in answers[0]
    assert "Recommended next step:" in answers[0]
    assert "Owner notification preview:" in answers[0]
    assert "Ниша: салон красоты" in answers[0]


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
