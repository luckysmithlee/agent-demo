"""单智能体运行时：统一轮次契约与工具注册表。

路由器检测意图，不选择智能体。所有请求由同一个智能体处理；检测出的意图
仅提供简短的行为提示，并收窄当前轮次可用的能力。工具权限由统一注册表和
能力策略决定，因此新增工具时无需修改各任务的处理表。
"""

from dataclasses import dataclass
from types import MappingProxyType
from typing import Callable, Mapping, Protocol

from .router import RouteResult, RuleBasedRouter, validate_request
from .rules import ROUTER_VERSION
from .task_types import TaskType


class Router(Protocol):
    """提供 ``route(request) -> RouteResult`` 的对象。"""

    def route(self, request: str) -> RouteResult: ...


@dataclass(frozen=True)
class ToolSpec:
    name: str
    description: str
    side_effects: bool = False
    network: bool = False


_TOOL_SPECS: tuple[ToolSpec, ...] = (
    ToolSpec("web_search", "Search external sources", network=True),
    ToolSpec("shell", "Run local shell commands", side_effects=True),
    ToolSpec("file_edit", "Modify repository files", side_effects=True),
    ToolSpec("run_tests", "Run the project test suite", side_effects=True),
)

TOOLS: Mapping[str, ToolSpec] = MappingProxyType(
    {spec.name: spec for spec in _TOOL_SPECS}
)


@dataclass(frozen=True)
class IntentCapability:
    """单智能体处理一种意图时可使用的能力。"""

    side_effects: bool = False
    network: bool = False


CAPABILITIES: Mapping[TaskType, IntentCapability] = MappingProxyType(
    {
        # chat 严格禁止使用任何工具。
        TaskType.CHAT: IntentCapability(),
        # research 可读取网络，但不能修改本机。
        TaskType.RESEARCH: IntentCapability(network=True),
        # coding 可使用完整的单智能体工具集。
        TaskType.CODING: IntentCapability(side_effects=True, network=True),
    }
)

GUIDANCE: Mapping[TaskType, str] = MappingProxyType(
    {
        TaskType.CHAT: "Answer directly from the conversation. Do not call any tool.",
        TaskType.RESEARCH: (
            "Search first and cite sources. Read-only tools only: never edit "
            "files or run shell commands."
        ),
        TaskType.CODING: (
            "Read the code before editing. Make the smallest change, run the "
            "tests, and report the exact commands you ran."
        ),
    }
)


class UnsupportedIntentError(ValueError):
    pass


class UnknownToolError(ValueError):
    pass


class ToolNotPermittedError(PermissionError):
    pass


@dataclass(frozen=True)
class ToolScope:
    """根据意图能力确定的当前轮次可用工具。"""

    intent: TaskType
    tools: frozenset[str]

    def allows(self, tool: str) -> bool:
        return tool in self.tools


@dataclass(frozen=True)
class AgentTurn:
    """单智能体处理一个用户请求所需的全部信息。"""

    request: str
    intent: TaskType
    confidence: float
    scope: ToolScope
    guidance: str
    reason: str = ""
    matched_keywords: tuple[str, ...] = ()
    router_version: str = ROUTER_VERSION
    fallback_recommended: bool = False


def capability_for(intent: TaskType) -> IntentCapability:
    try:
        return CAPABILITIES[intent]
    except KeyError as exc:
        raise UnsupportedIntentError(f"no capability profile for {intent!r}") from exc


def _permits(capability: IntentCapability, spec: ToolSpec) -> bool:
    if spec.side_effects and not capability.side_effects:
        return False
    if spec.network and not capability.network:
        return False
    return True


def scope_for(intent: TaskType) -> ToolScope:
    capability = capability_for(intent)
    return ToolScope(
        intent=intent,
        tools=frozenset(
            spec.name for spec in TOOLS.values() if _permits(capability, spec)
        ),
    )


def tool_allowed(intent: TaskType, tool: str) -> bool:
    return scope_for(intent).allows(tool)


class SingleAgent:
    """系统中唯一的智能体。

    ``router`` 可以是任何提供 ``route()`` 的对象（规则路由器、结构化 LLM
    路由器或测试替身）。``executors`` 将工具名映射到可调用对象，使实验
    可以离线测试；未注册的工具会明确报错，而不会假装运行成功。
    """

    def __init__(
        self,
        router: Router | None = None,
        executors: Mapping[str, Callable[..., str]] | None = None,
    ):
        self._router: Router = router if router is not None else RuleBasedRouter()
        self._executors: dict[str, Callable[..., str]] = {}
        for name, executor in (executors or {}).items():
            if name not in TOOLS:
                raise UnknownToolError(f"executor registered for unknown tool {name!r}")
            self._executors[name] = executor

    def begin(self, request: str) -> AgentTurn:
        """开始一个轮次；不切换处理器，只收窄工具范围。"""
        text = validate_request(request)
        result = self._router.route(text)
        intent = TaskType(result.task_type)
        return AgentTurn(
            request=text,
            intent=intent,
            confidence=result.confidence,
            scope=scope_for(intent),
            guidance=GUIDANCE[intent],
            reason=result.reason,
            matched_keywords=result.matched_keywords,
            router_version=result.router_version,
            fallback_recommended=result.fallback_recommended,
        )

    def call_tool(self, turn: AgentTurn, tool: str, **kwargs) -> str:
        """重新检查当前轮次的范围后执行工具。

        此处再次检查，是因为范围也是运行时保护，而不只是提示词中的提示。
        """
        if tool not in TOOLS:
            raise UnknownToolError(f"unknown tool {tool!r}")
        if not turn.scope.allows(tool):
            raise ToolNotPermittedError(
                f"tool {tool!r} is not available for {turn.intent.value} turns"
            )
        executor = self._executors.get(tool)
        if executor is None:
            raise RuntimeError(f"no executor registered for tool {tool!r}")
        return executor(**kwargs)
