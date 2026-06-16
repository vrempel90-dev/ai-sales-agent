from types import SimpleNamespace

from app.agents import AGENTS
from app.handlers.agents import get_command_name


def test_get_agent_by_string_commands():
    for command in ("posts", "dm", "audit", "proposal"):
        command_name = get_command_name(command)
        assert command_name in AGENTS
        assert AGENTS[command_name].command == command_name


def test_get_agent_by_command_object():
    command_name = get_command_name(SimpleNamespace(command="posts"))
    assert command_name == "/posts"
    assert command_name in AGENTS
