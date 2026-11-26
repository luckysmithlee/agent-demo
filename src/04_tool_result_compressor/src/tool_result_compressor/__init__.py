"""截断通用工具结果并提取测试日志摘要。"""

from typing import TypedDict


class TestOutputSummary(TypedDict):
    """测试日志的命中行数、关键行和末尾输出。"""

    failure_count: int
    important_lines: list[str]
    tail: list[str]


def compact_test_output(stdout: str, stderr: str) -> TestOutputSummary:
    """按标准输出、标准错误的顺序提取日志摘要。

    `failure_count` 统计命中关键词的行数，同一测试可能贡献多行。
    `important_lines` 保留最早的 50 条命中行，`tail` 保留末尾 80 行。
    """
    lines = stdout.splitlines() + stderr.splitlines()
    # shortcut: 按关键词匹配可能计入重复日志，需要统计失败用例时应读取测试报告。
    failures = [line for line in lines if "FAILED" in line or "ERROR" in line]
    return {
        "failure_count": len(failures),
        "important_lines": failures[:50],
        "tail": lines[-80:],
    }


def compress_tool_result(text: str, max_chars: int) -> str:
    """保留短结果；长结果保留首尾，并标注原文长度。

    预算使用 Python 的字符串长度（Unicode 码点数），而非字节数或 Token 数；
    截断标记也占预算。若标记和首尾各一个字符无法同时放入，或输入无效，
    则抛出 ValueError。
    """
    if not isinstance(text, str):
        raise ValueError("text must be a string")
    # bool 是 int 的子类，但不能作为字符预算。
    if isinstance(max_chars, bool) or not isinstance(max_chars, int) or max_chars < 1:
        raise ValueError("max_chars must be a positive integer")
    if len(text) <= max_chars:
        return text

    marker = f"\n...[原文 {len(text)} 字符，已截断]...\n"
    remaining = max_chars - len(marker)
    if remaining < 2:
        raise ValueError("max_chars is too small for the truncation marker and both ends")
    # 将剩余预算分给首尾；为奇数时，开头多保留一个字符。
    head = (remaining + 1) // 2
    tail = remaining - head
    # shortcut: 中间内容会丢失；需要保留语义或结构时改用针对工具的压缩策略。
    return text[:head] + marker + text[-tail:]
