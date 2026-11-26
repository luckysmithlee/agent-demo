"""可安全记录的路由事件。

原始请求文本不会离开此模块，只输出简短且稳定的指纹。
``tools_exposed`` 记录当前轮次的影响范围，即单智能体可以调用的工具，
而非实际调用过的工具。
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
    """对规范化请求生成短指纹；截断哈希可能碰撞，也不能防止猜测常见请求。"""
    normalized = normalize_text(request)
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:12]


def build_route_event(
    request: str, result: RouteResult, elapsed_ms: float
) -> RouteEvent:
    """将路由结果转成事件，并记录按任务类型允许使用的工具。"""
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
