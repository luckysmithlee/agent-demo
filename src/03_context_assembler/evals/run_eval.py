"""用本地场景数据验收上下文保留、截断和预算行为。"""

import json
from pathlib import Path

from context_assembler import ContextFragment, assemble_context

CASES_PATH = Path(__file__).with_name("context_cases.jsonl")


def run_eval(path: Path = CASES_PATH) -> dict:
    """比较 JSONL 样本的预期与实际结果，报告各案例未通过的字段。"""
    results = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        case = json.loads(line)
        fragments = [
            ContextFragment(**fragment) if isinstance(fragment, dict) else fragment
            for fragment in case["fragments"]
        ]
        context = assemble_context(
            case["instructions"], case["request"], fragments, case["max_chars"]
        )
        actual = {
            "instructions": context.instructions,
            "request": context.request,
            "max_chars": context.max_chars,
            "fragments": list(context.fragments),
            "skipped_indices": list(context.skipped_indices),
            "truncated_indices": list(context.truncated_indices),
            "used_chars": context.used_chars,
        }
        expected = {
            **case["expected"],
            "instructions": case["instructions"],
            "request": case["request"],
            "max_chars": case["max_chars"],
        }
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
