"""用本地工具输出验收通用截断与测试日志摘要。"""

import json
from pathlib import Path

from tool_result_compressor import compact_test_output, compress_tool_result

CASES_PATH = Path(__file__).with_name("compression_cases.jsonl")


def run_eval(path: Path = CASES_PATH) -> dict:
    """比较各 JSONL 案例的预期字段，返回通过数和失败明细。"""
    results = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        case = json.loads(line)
        if case["kind"] == "text":
            actual = {"output": compress_tool_result(**case["input"])}
        elif case["kind"] == "test-log":
            summary = compact_test_output(**case["input"])
            tail = summary["tail"]
            # 边界和行数足以验收长日志的窗口，无需在数据集中复制整个尾部。
            actual = {
                "failure_count": summary["failure_count"],
                "important_lines": summary["important_lines"],
                "tail_count": len(tail),
                "tail_first": tail[0] if tail else None,
                "tail_last": tail[-1] if tail else None,
            }
        else:
            raise ValueError(f"未知评测类型：{case['kind']!r}")

        expected = case["expected"]
        failed_fields = [field for field, value in actual.items() if value != expected[field]]
        results.append({"id": case["id"], "failed_fields": failed_fields})

    if not results:
        raise ValueError("评测集至少需要一个案例")
    return {
        "total": len(results),
        "passed": sum(not case["failed_fields"] for case in results),
        "cases": results,
    }


if __name__ == "__main__":
    report = run_eval()
    print(json.dumps(report, ensure_ascii=False, indent=2))
    raise SystemExit(0 if report["passed"] == report["total"] else 1)
