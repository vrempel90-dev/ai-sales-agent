import asyncio
from types import SimpleNamespace

from app.agents import AGENTS, FORBIDDEN_POST_PHRASES
from app.content_safety import validate_threads_post
from app.handlers.agents import generate_posts_response, get_command_name


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


def test_viral_niche_post_is_safe_and_ignores_forbidden_niche():
    from app.agents import viral_niche_post

    normal = viral_niche_post("стоматологии")
    unsafe_input = viral_niche_post("сайт и SEO")

    assert "стоматологии" in normal
    assert validate_threads_post(normal)[0]
    assert validate_threads_post(unsafe_input)[0]
    assert "сайт" not in unsafe_input.lower()
