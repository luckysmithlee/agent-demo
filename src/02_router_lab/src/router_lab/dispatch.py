"""Deprecated task-type dispatch table.

There are no per-task handlers anymore: a single agent owns one tool registry
and the intent only narrows the scope. This module stays importable for old
call sites and re-exports the single-agent API.
"""

from .agent import (
    ToolNotPermittedError,
    ToolScope,
    UnknownToolError,
    scope_for,
    tool_allowed,
)

__all__ = [
    "ToolNotPermittedError",
    "ToolScope",
    "UnknownToolError",
    "scope_for",
    "tool_allowed",
]
