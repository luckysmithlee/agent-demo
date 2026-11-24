"""Task type to handler contract, including allowed tools."""

from dataclasses import dataclass
from types import MappingProxyType
from typing import Mapping

from .task_types import TaskType


@dataclass(frozen=True)
class HandlerSpec:
    name: str
    allowed_tools: frozenset[str]


class UnsupportedTaskTypeError(ValueError):
    pass


_HANDLERS: dict[TaskType, HandlerSpec] = {
    TaskType.CHAT: HandlerSpec(name="chat", allowed_tools=frozenset()),
    TaskType.RESEARCH: HandlerSpec(
        name="research", allowed_tools=frozenset({"web_search"})
    ),
    TaskType.CODING: HandlerSpec(
        name="coding", allowed_tools=frozenset({"shell", "file_edit", "run_tests"})
    ),
}

HANDLERS: Mapping[TaskType, HandlerSpec] = MappingProxyType(_HANDLERS)


def handler_for(task_type: TaskType) -> HandlerSpec:
    try:
        return HANDLERS[task_type]
    except KeyError as exc:
        raise UnsupportedTaskTypeError(f"no handler for {task_type!r}") from exc


def tool_allowed(task_type: TaskType, tool: str) -> bool:
    return tool in handler_for(task_type).allowed_tools
