import pytest

from router_lab import InvalidRequestError, SingleAgent, TaskType
from router_lab.agent import (
    CAPABILITIES,
    GUIDANCE,
    TOOLS,
    ToolNotPermittedError,
    UnknownToolError,
    scope_for,
    tool_allowed,
)
from router_lab.router import RouteResult


def test_tool_registry_is_read_only():
    with pytest.raises(TypeError):
        TOOLS["browser"] = None


def test_every_intent_has_capability_and_guidance():
    assert set(CAPABILITIES) == set(TaskType)
    assert set(GUIDANCE) == set(TaskType)


def test_chat_scope_is_empty():
    assert scope_for(TaskType.CHAT).tools == frozenset()
    assert tool_allowed(TaskType.CHAT, "web_search") is False
    assert tool_allowed(TaskType.CHAT, "shell") is False


def test_research_scope_is_read_only():
    assert scope_for(TaskType.RESEARCH).tools == frozenset({"web_search"})
    assert tool_allowed(TaskType.RESEARCH, "file_edit") is False


def test_coding_scope_is_the_full_single_toolset():
    assert scope_for(TaskType.CODING).tools == frozenset(TOOLS)


def test_unknown_intent_is_rejected():
    with pytest.raises(ValueError):
        scope_for("unknown")
    with pytest.raises(ValueError):
        tool_allowed("unknown", "shell")


def test_begin_returns_one_turn_for_every_intent():
    request = "修复这个 Python 项目的测试"
    turn = SingleAgent().begin(request)

    assert turn.request == request
    assert turn.intent is TaskType.CODING
    assert turn.scope.intent is TaskType.CODING
    assert turn.guidance == GUIDANCE[TaskType.CODING]
    assert 0.0 <= turn.confidence <= 1.0
    assert turn.reason


def test_begin_validates_request():
    with pytest.raises(InvalidRequestError):
        SingleAgent().begin("   ")


def test_low_confidence_chat_keeps_empty_scope():
    turn = SingleAgent().begin("你好，随便聊聊")

    assert turn.intent is TaskType.CHAT
    assert turn.fallback_recommended is True
    assert turn.scope.tools == frozenset()


def test_router_is_injectable():
    class FakeRouter:
        def route(self, request):
            return RouteResult(
                task_type=TaskType.RESEARCH, confidence=0.93, reason="fake"
            )

    turn = SingleAgent(router=FakeRouter()).begin("随便什么问题")

    assert turn.intent is TaskType.RESEARCH
    assert turn.confidence == 0.93
    assert turn.scope.tools == frozenset({"web_search"})


def test_executors_only_accept_known_tools():
    with pytest.raises(UnknownToolError):
        SingleAgent(executors={"browser": lambda **kwargs: ""})


def test_call_tool_runs_injected_executor():
    agent = SingleAgent(executors={"web_search": lambda query: f"results:{query}"})
    turn = agent.begin("搜索今天最新的 Agent SDK 文章")

    assert agent.call_tool(turn, "web_search", query="agent sdk") == "results:agent sdk"


def test_call_tool_blocks_tools_outside_the_turn_scope():
    agent = SingleAgent(executors={"shell": lambda **kwargs: "boom"})
    turn = agent.begin("你好，随便聊聊")

    with pytest.raises(ToolNotPermittedError, match="chat"):
        agent.call_tool(turn, "shell", command="ls")


def test_research_turn_cannot_edit_files():
    agent = SingleAgent(executors={"file_edit": lambda **kwargs: "edited"})
    turn = agent.begin("调研最新的向量数据库方案")

    with pytest.raises(ToolNotPermittedError, match="research"):
        agent.call_tool(turn, "file_edit", path="README.md")


def test_call_tool_rejects_unknown_tool():
    agent = SingleAgent()
    turn = agent.begin("修复这个 bug")

    with pytest.raises(UnknownToolError):
        agent.call_tool(turn, "browser")


def test_call_tool_requires_a_registered_executor():
    agent = SingleAgent()
    turn = agent.begin("修复这个 bug")

    with pytest.raises(RuntimeError, match="no executor"):
        agent.call_tool(turn, "run_tests")
