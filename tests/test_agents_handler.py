import asyncio
from types import SimpleNamespace

from app.agents import AGENTS, FORBIDDEN_POST_PHRASES
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

    assert 300 <= len(post) <= 700
    assert "ai-бот" in normalized
    assert "crm" in normalized
    assert not any(phrase in normalized for phrase in FORBIDDEN_POST_PHRASES)


def test_threads_post_clinic_fallback():
    from app.agents import fallback_threads_post

    post = fallback_threads_post("AI-администратор для клиники")
    normalized = post.lower()

    assert 300 <= len(post) <= 700
    assert "клиника" in normalized
    assert "противопоказания" in normalized
    assert "это не заменяет врача" in normalized
    assert not any(phrase in normalized for phrase in FORBIDDEN_POST_PHRASES)


def test_threads_day_creates_five_fallback_posts():
    from app.agents import fallback_threads_day_posts

    posts = fallback_threads_day_posts()

    assert len(posts) == 5
    assert all(300 <= len(post) <= 700 for post in posts)
    assert not any(
        phrase in " ".join(posts).lower()
        for phrase in FORBIDDEN_POST_PHRASES
    )


def test_unsafe_generated_threads_post_uses_fallback():
    from app.agents import safe_threads_post

    generated = "Конечно! Вот короткий Threads-пост про уникальный AI-бот."
    post = safe_threads_post("AI-администратор для клиники", generated)

    assert post != generated
    assert "Клиника может терять заявки" in post
