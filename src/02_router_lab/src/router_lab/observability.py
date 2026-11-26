"""Route event records that are safe to log.

Raw request text never leaves this module; only a short stable fingerprint.
``tools_exposed`` records the blast radius of a turn: which tools the single
agent could have called, not which ones it did call.
"""

import hashlib
from dataclasses import dataclass

from .agent import scope_for
from .router import RouteResult, normalize_text


@dataclass(frozen=True)
class RouteEvent:
    request_fingerprint: str
    task_type: str
    confidence: float
    fallback_recommended: bool
    matched_keywords: tuple[str, ...]
    router_version: str
    elapsed_ms: float
    tools_exposed: tuple[str, ...] = ()


def request_fingerprint(request: str) -> str:
    normalized = normalize_text(request)
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:12]


def build_route_event(
    request: str, result: RouteResult, elapsed_ms: float
) -> RouteEvent:
    return RouteEvent(
        request_fingerprint=request_fingerprint(request),
        task_type=result.task_type.value,
        confidence=result.confidence,
        fallback_recommended=result.fallback_recommended,
        matched_keywords=result.matched_keywords,
        router_version=result.router_version,
        elapsed_ms=round(elapsed_ms, 4),
        tools_exposed=tuple(sorted(scope_for(result.task_type).tools)),
    )
