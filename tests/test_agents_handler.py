import asyncio
from types import SimpleNamespace

from app.agents import AGENTS, FORBIDDEN_POST_PHRASES, MARKETING_ANGLES, VIRAL_THREADS_TEMPLATES
from app.content_safety import validate_threads_post
from app.handlers.agents import generate_posts_response, get_command_name
from app.threads_growth import has_specific_ai_solution, has_strong_cta, validate_growth_post


def test_get_agent_by_string_commands():
    for command in ("posts", "dm", "audit", "proposal"):
        command_name = get_command_name(command)
        assert command_name in AGENTS
        assert AGENTS[command_name].command == command_name


def test_get_agent_by_command_object():
    command_name = get_command_name(SimpleNamespace(command="posts"))
    assert command_name == "/posts"
    assert command_name in AGENTS


def test_generate_posts_response_is_fallback_first(monkeypatch):
    async def fail_if_called(*args, **kwargs):
        raise AssertionError("/posts must not call Ollama")

    monkeypatch.setattr("app.handlers.agents.ask_ollama", fail_if_called)

    response = asyncio.run(generate_posts_response(None, "салон красоты"))
    posts = [post for post in response.split("\n\n") if post.strip()]
    normalized = response.lower()

    assert len(posts) == 10
    assert "ai-бот" in normalized or "ai-администратор" in normalized
    assert "crm" in normalized
    assert "follow-up" in normalized
    assert "админ" in normalized
    assert "заяв" in normalized
    assert not any(phrase in normalized for phrase in FORBIDDEN_POST_PHRASES)


def test_threads_post_is_fallback_first(monkeypatch):
    from app.agents import fallback_threads_post

    async def fail_if_called(*args, **kwargs):
        raise AssertionError("/threads_post must not call Ollama")

    monkeypatch.setattr("app.handlers.agents.ask_ollama", fail_if_called)

    post = fallback_threads_post("AI-бот для ресторана")
    normalized = post.lower()

    assert 250 <= len(post) <= 450
    assert "ai-бот" in normalized
    assert "crm" in normalized
    assert not any(phrase in normalized for phrase in FORBIDDEN_POST_PHRASES)


def test_threads_post_clinic_fallback():
    from app.agents import fallback_threads_post

    post = fallback_threads_post("AI-администратор для клиники")
    normalized = post.lower()

    assert 250 <= len(post) <= 450
    assert "клинику" in normalized
    assert "противопоказания" in normalized
    assert "ai-администратор" in normalized
    assert not any(phrase in normalized for phrase in FORBIDDEN_POST_PHRASES)


def test_threads_day_creates_five_fallback_posts():
    from app.agents import fallback_threads_day_posts

    posts = fallback_threads_day_posts()

    assert len(posts) == 5
    assert all(200 <= len(post) <= 700 for post in posts)
    assert not any(
        phrase in " ".join(posts).lower()
        for phrase in FORBIDDEN_POST_PHRASES
    )


def test_unsafe_generated_threads_post_uses_fallback():
    from app.agents import safe_threads_post

    generated = "Конечно! Вот короткий Threads-пост про уникальный AI-бот."
    post = safe_threads_post("AI-администратор для клиники", generated)

    assert post != generated
    assert "Пациент написал в клинику" in post
    assert "Напишите «бот»" in post


def test_threads_cta_uses_public_telegram_link(monkeypatch):
    from app.agents import viral_threads_day_posts

    monkeypatch.setenv("PUBLIC_TELEGRAM_BOT_LINK", "https://t.me/your_bot_username")

    posts = viral_threads_day_posts()

    assert any("Напишите «бот» в Telegram" in post for post in posts)
    assert any("https://t.me/your_bot_username" in post for post in posts)
    assert any("в личку" in post for post in posts)
    assert not all("https://t.me/your_bot_username" in post for post in posts)


def test_viral_threads_day_has_seven_safe_templates():
    from app.agents import viral_threads_day_posts

    posts = viral_threads_day_posts()

    assert len(posts) == 7
    assert all(300 <= len(post) <= 700 for post in posts)
    assert all(validate_threads_post(post)[0] for post in posts)
    assert all("AI-" in post or "AI-" in post.upper() for post in posts)
    assert all("https://wa.me/" not in post for post in posts)


def test_fallback_templates_have_senior_marketing_components():
    assert len(MARKETING_ANGLES) == 18
    for post in VIRAL_THREADS_TEMPLATES:
        assert 300 <= len(post) <= 700
        assert 2 <= len(post.split("\n\n")) <= 4
        assert has_specific_ai_solution(post)
        assert has_strong_cta(post)
        assert validate_growth_post(post)[0]


def test_viral_niche_post_is_safe_and_ignores_forbidden_niche():
    from app.agents import viral_niche_post

    normal = viral_niche_post("стоматологии")
    unsafe_input = viral_niche_post("сайт и SEO")

    assert "стоматологии" in normal
    assert validate_threads_post(normal)[0]
    assert validate_threads_post(unsafe_input)[0]
    assert "сайт" not in unsafe_input.lower()


def test_threads_next_can_render_post_with_keyboard(monkeypatch):
    from app.handlers import agents
    from app.post_queue import QueuedPost

    post = QueuedPost(id="42", text="AI-администратор отвечает первым и не теряет заявки из Direct.", status="draft", created_at="now")
    sent = []

    class FakeMessage:
        async def answer(self, text, **kwargs):
            sent.append((text, kwargs))

    monkeypatch.setattr(agents, "next_unique_publishable_post", lambda _queue: post)

    asyncio.run(agents.threads_next(FakeMessage(), SimpleNamespace(brand_lead_agent_enabled=False)))

    assert sent
    assert "Threads draft #42" in sent[0][0]
    assert sent[0][1]["reply_markup"].model_dump()["inline_keyboard"][0][0]["callback_data"] == "threads:publish:42"


def test_offer_post_can_render_post_with_keyboard(monkeypatch):
    from app.handlers import agents
    from app.post_queue import QueuedPost

    post = QueuedPost(id="7", text="AI-администратор закрывает первый ответ и follow-up.", status="draft", created_at="now")
    sent = []

    class FakeMessage:
        async def answer(self, text, **kwargs):
            sent.append((text, kwargs))

    monkeypatch.setattr(agents, "add_strong_unique_post", lambda *_args, **_kwargs: post)

    asyncio.run(agents.offer_post(FakeMessage(), SimpleNamespace(client_acquisition_main_keyword="разбор", client_acquisition_daily_offer_post_hour=18, brand_lead_agent_enabled=False)))

    assert sent
    assert "Threads draft #7" in sent[0][0]
    assert sent[0][1]["reply_markup"].model_dump()["inline_keyboard"][0][0]["callback_data"] == "threads:publish:7"
