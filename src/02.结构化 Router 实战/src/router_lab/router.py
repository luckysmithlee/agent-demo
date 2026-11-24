import re
import unicodedata
from dataclasses import dataclass
from time import perf_counter

from .rules import CODING_RULES, RESEARCH_RULES, ROUTER_VERSION, KeywordRule
from .task_types import TaskType

MAX_REQUEST_LENGTH = 10_000

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
    task_type: TaskType
    confidence: float
    reason: str = ""
    matched_keywords: tuple[str, ...] = ()
    router_version: str = ROUTER_VERSION
    fallback_recommended: bool = False


@dataclass(frozen=True)
class RouteConfig:
    min_score: int = 2
    confidence_threshold: float = 0.70


def normalize_text(text: str) -> str:
    """NFKC-normalize, lowercase, and collapse whitespace."""
    normalized = unicodedata.normalize("NFKC", text).lower()
    return re.sub(r"\s+", " ", normalized).strip()


def validate_request(request: str, max_length: int = MAX_REQUEST_LENGTH) -> str:
    if not isinstance(request, str):
        raise InvalidRequestError("request must be a string")

    text = request.strip()
    if not text:
        raise InvalidRequestError("request must not be empty")
    if len(text) > max_length:
        raise InvalidRequestError("request exceeds maximum length")
    return text


def match_rules(text: str, rules: tuple[KeywordRule, ...]) -> list[KeywordRule]:
    """Return rules that match ``text``. Input must be normalized."""
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
    base = 0.60 + 0.06 * score
    margin_bonus = min(0.12, 0.03 * max(0, margin))
    return round(min(0.98, base + margin_bonus), 2)


class RuleBasedRouter:
    """Deterministic router. Scores keyword evidence instead of first-match."""

    MAX_REQUEST_LENGTH = MAX_REQUEST_LENGTH

    def __init__(self, config: RouteConfig | None = None):
        self.config = config or RouteConfig()

    def route(self, request: str) -> RouteResult:
        text = validate_request(request, self.MAX_REQUEST_LENGTH)
        normalized = normalize_text(text)

        coding_hits = match_rules(normalized, CODING_RULES)
        research_hits = match_rules(normalized, RESEARCH_RULES)
        coding_score = score_hits(coding_hits)
        research_score = score_hits(research_hits)

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
    """Public convenience API for the default router."""
    return RuleBasedRouter().route(request)


def measure_route(request: str) -> tuple[RouteResult, float]:
    """Route a request and return the result with elapsed milliseconds."""
    started_at = perf_counter()
    result = route_request(request)
    elapsed_ms = (perf_counter() - started_at) * 1000
    return result, elapsed_ms
