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
