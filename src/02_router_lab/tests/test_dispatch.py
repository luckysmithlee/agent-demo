"""The old per-task dispatch table is gone; check the deprecated alias only."""

from router_lab import agent
from router_lab import dispatch
from router_lab.task_types import TaskType


def test_deprecated_module_reuses_the_single_agent_scope():
    assert dispatch.scope_for is agent.scope_for
    assert dispatch.tool_allowed is agent.tool_allowed


def test_scope_still_protects_chat_through_the_alias():
    assert dispatch.tool_allowed(TaskType.CHAT, "web_search") is False
    assert dispatch.tool_allowed(TaskType.RESEARCH, "web_search") is True
