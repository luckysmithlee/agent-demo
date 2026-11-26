import pytest

from router_lab import (
    InvalidRequestError,
    RouteConfig,
    RuleBasedRouter,
    TaskType,
)
from router_lab.rules import ROUTER_VERSION


@pytest.fixture
def router():
    return RuleBasedRouter()


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("解释 TCP 三次握手", TaskType.CHAT),
        ("搜索今天最新的 Agent SDK 变化", TaskType.RESEARCH),
        ("修复这个 Python 项目测试", TaskType.CODING),
    ],
)
def test_routes_representative_requests(router, text, expected):
    result = router.route(text)

    assert result.task_type is expected
    assert 0.0 <= result.confidence <= 1.0
    assert result.reason
    assert result.router_version == ROUTER_VERSION


@pytest.mark.parametrize("text", ["", "   ", None, 123])
def test_rejects_invalid_requests(router, text):
    with pytest.raises(InvalidRequestError):
        router.route(text)


def test_rejects_oversized_requests(router):
    with pytest.raises(InvalidRequestError):
        router.route("x" * (router.MAX_REQUEST_LENGTH + 1))


def test_research_wins_when_it_has_more_evidence(router):
    # 回归：过去一个 coding 关键词会胜过四个 research 关键词。
    result = router.route("找出 PostgreSQL 最近版本修复的安全漏洞摘要")

    assert result.task_type is TaskType.RESEARCH


def test_ascii_keywords_use_word_boundaries(router):
    # “code”不能匹配“barcode”的一部分，“fix”不能匹配“prefix”的一部分。
    assert router.route("用 barcode 举例说明前缀树").task_type is TaskType.CHAT
    assert router.route("解释 prefix 的含义").task_type is TaskType.CHAT


def test_fullwidth_characters_are_normalized(router):
    result = router.route("请介绍 ｒｅａｃｔ 和 ｖｕｅ 的区别")

    assert result.task_type is TaskType.CHAT


def test_keyword_gap_regression(router):
    # 回归：此 coding 请求过去会错误地落入 chat。
    result = router.route("在 React 页面中增加加载、空状态和错误重试状态")

    assert result.task_type is TaskType.CODING


def test_no_evidence_defaults_to_chat_with_fallback(router):
    result = router.route("你好，随便聊聊")

    assert result.task_type is TaskType.CHAT
    assert result.confidence == 0.50
    assert result.fallback_recommended is True


def test_weak_evidence_defaults_to_chat_with_fallback(router):
    result = router.route("用通俗语言说明为什么哈希表查找平均是 O(1)")

    assert result.task_type is TaskType.CHAT
    assert result.confidence == 0.55
    assert result.fallback_recommended is True
    assert "查找" in result.matched_keywords


def test_tie_defaults_to_chat_with_fallback(router):
    # coding：代码 + bug = 2；research：找出 = 2。
    result = router.route("找出代码里的 bug")

    assert result.task_type is TaskType.CHAT
    assert result.fallback_recommended is True
    assert "ambiguous" in result.reason


def test_english_keywords_are_case_insensitive(router):
    result = router.route("FIX the BUG in this module")

    assert result.task_type is TaskType.CODING


def test_more_evidence_raises_confidence(router):
    single = router.route("搜索 Agent SDK")
    multiple = router.route("搜索今天最新的 Agent SDK 文章")

    assert single.task_type is TaskType.RESEARCH
    assert multiple.task_type is TaskType.RESEARCH
    assert multiple.confidence > single.confidence
    assert multiple.confidence <= 0.98


def test_confidence_threshold_is_configurable():
    strict = RuleBasedRouter(RouteConfig(confidence_threshold=0.99))
    result = strict.route("修复这个 bug")

    assert result.task_type is TaskType.CODING
    assert result.fallback_recommended is True


def test_min_score_is_configurable():
    lenient = RuleBasedRouter(RouteConfig(min_score=1))
    result = lenient.route("比较同步和异步 I/O 的区别")

    assert result.task_type is TaskType.RESEARCH


def test_routing_is_deterministic(router):
    first = router.route("修复 Docker 构建失败并更新 Dockerfile")
    second = router.route("修复 Docker 构建失败并更新 Dockerfile")

    assert first == second


def test_result_contains_matched_keywords(router):
    result = router.route("修复 CI 里的 lint 报错并补充单元测试")

    assert result.task_type is TaskType.CODING
    assert "修复" in result.matched_keywords
    assert "单元测试" in result.matched_keywords
