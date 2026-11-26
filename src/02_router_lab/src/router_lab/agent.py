"""Single-agent runtime: one turn contract, one tool registry.

The router is an intent detector, not an agent selector. Every request is
handled by the same agent; the detected intent only supplies a short behavior
hint and narrows which capabilities are exposed for that turn. Tool
permissions are derived from one registry plus a capability policy, so adding
a tool never means editing a per-task handler table.
"""

from dataclasses import dataclass
from types import MappingProxyType
from typing import Callable, Mapping, Protocol

from .router import RouteResult, RuleBasedRouter, validate_request
from .rules import ROUTER_VERSION
from .task_types import TaskType


class Router(Protocol):
    """Anything exposing ``route(request) -> RouteResult``."""

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
    """Capabilities the single agent may use while handling one intent."""

    side_effects: bool = False
    network: bool = False


CAPABILITIES: Mapping[TaskType, IntentCapability] = MappingProxyType(
    {
        # chat keeps the hard invariant: no tools at all.
        TaskType.CHAT: IntentCapability(),
        # research may read the network but must not change the machine.
        TaskType.RESEARCH: IntentCapability(network=True),
        # coding gets the full single-agent toolset.
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
    """Tools exposed for one turn, derived from the intent capability."""

    intent: TaskType
    tools: frozenset[str]

    def allows(self, tool: str) -> bool:
        return tool in self.tools


@dataclass(frozen=True)
class AgentTurn:
    """Everything the single agent loop needs for one user request."""

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
    """The only agent in the system.

    ``router`` is any object with ``route()`` (rule router, structured LLM
    router, or a test double). ``executors`` maps tool names to callables so
    the lab stays offline-testable; unregistered tools fail loudly instead of
    silently pretending to run.
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
        """Start a turn. There is no handler switch: only the scope narrows."""
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
        """Execute a tool after re-checking the turn scope.

        The check is repeated here on purpose: the scope is a runtime guard,
        not just a hint in the prompt.
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
