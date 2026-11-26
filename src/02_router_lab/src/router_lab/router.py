import re
import unicodedata
from dataclasses import dataclass
from time import perf_counter

from .rules import CODING_RULES, RESEARCH_RULES, ROUTER_VERSION, KeywordRule
from .task_types import TaskType

MAX_REQUEST_LENGTH = 10_000

# 英文关键词按 ASCII 单词边界匹配，避免 code 误命中 barcode；中文仍按子串匹配。
_ASCII_PATTERNS: dict[str, re.Pattern[str]] = {
    rule.keyword: re.compile(
        rf"(?<![a-z0-9_]){re.escape(rule.keyword)}(?![a-z0-9_])"
    )
    for rule in (*CODING_RULES, *RESEARCH_RULES)
    if rule.keyword.isascii()
}


class InvalidRequestError(ValueError):
    pass


@dataclass(frozen=True)
class RouteResult:
    """路由结论及其依据；fallback_recommended 只是建议，不会自动执行回退。"""

    task_type: TaskType
    confidence: float
    reason: str = ""
    matched_keywords: tuple[str, ...] = ()
    router_version: str = ROUTER_VERSION
    fallback_recommended: bool = False


@dataclass(frozen=True)
class RouteConfig:
    """min_score 控制最低证据分数，confidence_threshold 控制回退建议。"""

    min_score: int = 2
    confidence_threshold: float = 0.70


def normalize_text(text: str) -> str:
    """统一全角等兼容字符、大小写和空白，使写法不同的请求更容易匹配。"""
    normalized = unicodedata.normalize("NFKC", text).lower()
    return re.sub(r"\s+", " ", normalized).strip()


def validate_request(request: str, max_length: int = MAX_REQUEST_LENGTH) -> str:
    """返回去除首尾空白的请求；非字符串、空请求或超长时抛出 InvalidRequestError。"""
    if not isinstance(request, str):
        raise InvalidRequestError("request must be a string")

    text = request.strip()
    if not text:
        raise InvalidRequestError("request must not be empty")
    if len(text) > max_length:
        raise InvalidRequestError("request exceeds maximum length")
    return text


def match_rules(text: str, rules: tuple[KeywordRule, ...]) -> list[KeywordRule]:
    """返回匹配 ``text`` 的规则；输入必须已规范化，每条规则最多计一次。"""
    hits = []
    for rule in rules:
        if rule.keyword.isascii():
            if _ASCII_PATTERNS[rule.keyword].search(text):
                hits.append(rule)
        elif rule.keyword in text:
            hits.append(rule)
    return hits


def score_hits(hits: list[KeywordRule]) -> int:
    return sum(rule.weight for rule in hits)


def _confidence(score: int, margin: int) -> float:
    # 这是基于得分和分差的启发式数值，不是经过校准的概率。
    base = 0.60 + 0.06 * score
    margin_bonus = min(0.12, 0.03 * max(0, margin))
    return round(min(0.98, base + margin_bonus), 2)


class RuleBasedRouter:
    """确定性路由器，根据关键词证据评分，而非取首个匹配。"""

    MAX_REQUEST_LENGTH = MAX_REQUEST_LENGTH

    def __init__(self, config: RouteConfig | None = None):
        self.config = config or RouteConfig()

    def route(self, request: str) -> RouteResult:
        """校验请求并比较两类关键词权重，返回类型、依据和回退建议。"""
        text = validate_request(request, self.MAX_REQUEST_LENGTH)
        normalized = normalize_text(text)

        coding_hits = match_rules(normalized, CODING_RULES)
        research_hits = match_rules(normalized, RESEARCH_RULES)
        coding_score = score_hits(coding_hits)
        research_score = score_hits(research_hits)

        # 证据不足或双方平分时保守地归为 chat，并建议调用方进一步处理。
        if coding_score < self.config.min_score and research_score < self.config.min_score:
            matched = tuple(rule.keyword for rule in (*coding_hits, *research_hits))
            if coding_score == 0 and research_score == 0:
                reason = "no keyword evidence; default to chat"
                confidence = 0.50
            else:
                reason = (
                    f"weak evidence only (coding={coding_score}, "
                    f"research={research_score}); default to chat"
                )
                confidence = 0.55
            return RouteResult(
                task_type=TaskType.CHAT,
                confidence=confidence,
                reason=reason,
                matched_keywords=matched,
                fallback_recommended=True,
            )

        if coding_score == research_score:
            matched = tuple(rule.keyword for rule in (*coding_hits, *research_hits))
            return RouteResult(
                task_type=TaskType.CHAT,
                confidence=0.55,
                reason=(
                    f"ambiguous evidence (coding={coding_score}, "
                    f"research={research_score}); default to chat"
                ),
                matched_keywords=matched,
                fallback_recommended=True,
            )

        if coding_score > research_score:
            task_type, hits = TaskType.CODING, coding_hits
            top, other = coding_score, research_score
        else:
            task_type, hits = TaskType.RESEARCH, research_hits
            top, other = research_score, coding_score

        confidence = _confidence(top, top - other)
        return RouteResult(
            task_type=task_type,
            confidence=confidence,
            reason=(
                f"{task_type.value} evidence wins (coding={coding_score}, "
                f"research={research_score}, margin={top - other})"
            ),
            matched_keywords=tuple(rule.keyword for rule in hits),
            fallback_recommended=confidence < self.config.confidence_threshold,
        )


def route_request(request: str) -> RouteResult:
    """默认路由器的公共便捷接口。"""
    return RuleBasedRouter().route(request)


def measure_route(request: str) -> tuple[RouteResult, float]:
    """路由请求并返回结果和耗时（毫秒）。"""
    started_at = perf_counter()
    result = route_request(request)
    elapsed_ms = (perf_counter() - started_at) * 1000
    return result, elapsed_ms
