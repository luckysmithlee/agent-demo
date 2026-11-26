"""用本地场地证据验收策划草案的预算、选址和审批边界。"""

import json
from pathlib import Path

from event_planner import Venue, plan_meetup

CASES_PATH = Path(__file__).with_name("event_cases.jsonl")


def run_eval(path: Path = CASES_PATH) -> dict:
    """比较 JSONL 样本的预期与实际草案，报告不匹配的字段。"""
    results = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        case = json.loads(line)
        venues = [Venue(**venue) for venue in case["venues"]]
        plan = plan_meetup(case["event_time"], venues)
        candidates = plan["场地候选"]
        costs = plan["预算明细（元）"]
        actual = {
            "event_time": plan["时间"],
            "candidate_sources": [candidate["依据"] for candidate in candidates],
            "candidate_statuses": [candidate["判断"] for candidate in candidates],
            "selected_venue": plan["拟选场地"],
            # 场地费用待确认时，茶歇等已知支出只是整场预算的一部分。
            "estimated_total_yuan": None if costs["场地"] is None else sum(costs.values()),
            "publish_approval": plan["发布审批"],
            "proposed_actions": plan["拟提交审批的操作"],
        }
        expected = {
            **case["expected"],
            "event_time": case["event_time"],
            "candidate_sources": [venue.source for venue in venues],
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
