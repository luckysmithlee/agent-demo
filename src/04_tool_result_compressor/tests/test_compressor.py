import pytest

from tool_result_compressor import compact_test_output, compress_tool_result


def test_compact_test_output_keeps_middle_failures_and_stderr():
    stdout = "开始\nFAILED tests/test_plan.py\n" + "通过\n" * 85
    stderr = "ERROR fixture\n退出码 1\n"

    summary = compact_test_output(stdout, stderr)

    assert summary["failure_count"] == 2
    assert summary["important_lines"] == ["FAILED tests/test_plan.py", "ERROR fixture"]
    assert summary["tail"] == ["通过"] * 78 + ["ERROR fixture", "退出码 1"]


def test_compact_test_output_limits_important_lines_without_limiting_count():
    failures = [f"FAILED {index}" for index in range(55)]
    summary = compact_test_output("\n".join(failures), "ERROR teardown")

    assert summary == {
        "failure_count": 56,
        "important_lines": failures[:50],
        "tail": failures + ["ERROR teardown"],
    }


def test_compact_test_output_with_no_logs():
    assert compact_test_output("", "") == {"failure_count": 0, "important_lines": [], "tail": []}


def test_short_result_is_unchanged_including_whitespace():
    assert compress_tool_result(" 结果\n", 4) == " 结果\n"
    assert compress_tool_result("", 1) == ""


def test_long_result_keeps_both_ends_and_marks_original_length():
    text = "ERROR: " + "中" * 80 + "\nexit code: 1"
    result = compress_tool_result(text, 48)
    assert len(result) == 48
    assert result.startswith("ERROR: ")
    assert result.endswith("exit code: 1")
    assert f"原文 {len(text)} 字符，已截断" in result


def test_marker_must_fit_with_both_ends():
    text = "x" * 100
    marker = f"\n...[原文 {len(text)} 字符，已截断]...\n"
    with pytest.raises(ValueError, match="too small"):
        compress_tool_result(text, len(marker) + 1)
    assert compress_tool_result(text, len(marker) + 2) == "x" + marker + "x"


@pytest.mark.parametrize("text, budget", [(None, 10), ([], 10), ("text", 0), ("text", True), ("text", 1.5)])
def test_invalid_input(text, budget):
    with pytest.raises(ValueError):
        compress_tool_result(text, budget)
