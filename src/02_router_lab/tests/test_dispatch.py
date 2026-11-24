import pytest

from router_lab.dispatch import (
    HANDLERS,
    UnsupportedTaskTypeError,
    handler_for,
    tool_allowed,
)
from router_lab.task_types import TaskType


def test_chat_has_no_tools():
    spec = handler_for(TaskType.CHAT)

    assert spec.allowed_tools == frozenset()
    assert tool_allowed(TaskType.CHAT, "web_search") is False
    assert tool_allowed(TaskType.CHAT, "shell") is False


def test_research_allows_only_web_search():
    assert tool_allowed(TaskType.RESEARCH, "web_search") is True
    assert tool_allowed(TaskType.RESEARCH, "shell") is False


def test_coding_tools_are_whitelisted():
    assert tool_allowed(TaskType.CODING, "shell") is True
    assert tool_allowed(TaskType.CODING, "file_edit") is True
    assert tool_allowed(TaskType.CODING, "web_search") is False


def test_handler_registry_is_read_only():
    with pytest.raises(TypeError):
        HANDLERS[TaskType.CHAT] = None


def test_unknown_task_type_is_rejected():
    with pytest.raises(UnsupportedTaskTypeError):
        handler_for("unknown")

    with pytest.raises(UnsupportedTaskTypeError):
        tool_allowed("unknown", "shell")
