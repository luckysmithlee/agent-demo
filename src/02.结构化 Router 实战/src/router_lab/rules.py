"""Versioned keyword rules for the deterministic router.

Weights encode evidence strength:

* 2 points: the keyword is strong evidence for the task type.
* 1 point: the keyword is ambiguous on its own. It only counts when it
  combines with another signal, which keeps false positives down.
"""

from dataclasses import dataclass

ROUTER_VERSION = "2.0.0"

STRONG = 2
WEAK = 1


@dataclass(frozen=True)
class KeywordRule:
    keyword: str
    weight: int


CODING_RULES: tuple[KeywordRule, ...] = (
    KeywordRule("修复", STRONG),
    KeywordRule("实现", STRONG),
    KeywordRule("重构", STRONG),
    KeywordRule("定位异常", STRONG),
    KeywordRule("单元测试", STRONG),
    KeywordRule("集成测试", STRONG),
    KeywordRule("边界条件", STRONG),
    KeywordRule("优化这条", STRONG),
    KeywordRule("新增", STRONG),
    KeywordRule("接入", STRONG),
    KeywordRule("改造", STRONG),
    KeywordRule("排查", STRONG),
    KeywordRule("dockerfile", STRONG),
    KeywordRule("docker构建", STRONG),
    KeywordRule("react页面", STRONG),
    KeywordRule("unit test", STRONG),
    KeywordRule("sql", STRONG),
    KeywordRule("接口", WEAK),
    KeywordRule("代码", WEAK),
    KeywordRule("仓库", WEAK),
    KeywordRule("编写", WEAK),
    KeywordRule("异常", WEAK),
    KeywordRule("优化", WEAK),
    KeywordRule("页面", WEAK),
    KeywordRule("测试", WEAK),
    KeywordRule("错误", WEAK),
    KeywordRule("docker", WEAK),
    KeywordRule("react", WEAK),
    KeywordRule("python", WEAK),
    KeywordRule("fastapi", WEAK),
    KeywordRule("asyncio", WEAK),
    KeywordRule("api", WEAK),
    KeywordRule("bug", WEAK),
    KeywordRule("code", WEAK),
    KeywordRule("refactor", WEAK),
    KeywordRule("fix", WEAK),
    KeywordRule("implement", WEAK),
)

RESEARCH_RULES: tuple[KeywordRule, ...] = (
    KeywordRule("搜索", STRONG),
    KeywordRule("调研", STRONG),
    KeywordRule("调查", STRONG),
    KeywordRule("研究", STRONG),
    KeywordRule("找出", STRONG),
    KeywordRule("最新", STRONG),
    KeywordRule("最近", STRONG),
    KeywordRule("news", STRONG),
    KeywordRule("查找", WEAK),
    KeywordRule("查询", WEAK),
    KeywordRule("查看", WEAK),
    KeywordRule("看看", WEAK),
    KeywordRule("核实", WEAK),
    KeywordRule("当前", WEAK),
    KeywordRule("更新", WEAK),
    KeywordRule("版本", WEAK),
    KeywordRule("比较", WEAK),
    KeywordRule("差异", WEAK),
    KeywordRule("安全", WEAK),
    KeywordRule("主流", WEAK),
    KeywordRule("今天", WEAK),
    KeywordRule("论文", WEAK),
    KeywordRule("文章", WEAK),
    KeywordRule("技术", WEAK),
    KeywordRule("compare", WEAK),
    KeywordRule("security", WEAK),
)
