import argparse
import json
import sys
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from time import perf_counter_ns
from typing import Iterable

from .router import RuleBasedRouter, normalize_text
from .rules import ROUTER_VERSION
from .task_types import TaskType

EVALS_DIR = Path(__file__).resolve().parents[2] / "evals"
DEFAULT_DATASETS = (
    EVALS_DIR / "router_requests.jsonl",
    EVALS_DIR / "router_holdout.jsonl",
)

LABELS = tuple(task.value for task in TaskType)
REQUIRED_KEYS = {"request", "expected_task"}


class DatasetError(ValueError):
    pass


@dataclass(frozen=True)
class GateThresholds:
    min_accuracy: float = 0.90
    max_false_tool_rate: float = 0.05
    max_p95_latency_ms: float = 5.0

    def __post_init__(self) -> None:
        if not 0.0 <= self.min_accuracy <= 1.0:
            raise ValueError("min_accuracy must be within [0, 1]")
        if not 0.0 <= self.max_false_tool_rate <= 1.0:
            raise ValueError("max_false_tool_rate must be within [0, 1]")
        if self.max_p95_latency_ms <= 0:
            raise ValueError("max_p95_latency_ms must be positive")


@dataclass
class DatasetStats:
    total: int = 0
    correct: int = 0
    false_tool_count: int = 0
    chat_support: int = 0
    latencies_ms: list[float] = field(default_factory=list)
    confusion: dict[str, dict[str, int]] = field(
        default_factory=lambda: {label: dict.fromkeys(LABELS, 0) for label in LABELS}
    )
    confidence_buckets: dict[str, list[int]] = field(
        default_factory=lambda: {
            "0.0-0.5": [0, 0],
            "0.5-0.7": [0, 0],
            "0.7-0.9": [0, 0],
            "0.9-1.0": [0, 0],
        }
    )


def _confidence_bucket(confidence: float) -> str:
    if confidence < 0.5:
        return "0.0-0.5"
    if confidence < 0.7:
        return "0.5-0.7"
    if confidence < 0.9:
        return "0.7-0.9"
    return "0.9-1.0"


def load_rows(path: Path) -> list[dict[str, str]]:
    """读取并校验 JSONL；按规范化后的请求去重，拒绝空数据集。"""
    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, 1):
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError as exc:
                raise DatasetError(f"{path.name}:{line_number}: invalid JSON") from exc
            if not isinstance(row, dict) or set(row) != REQUIRED_KEYS:
                raise DatasetError(
                    f"{path.name}:{line_number}: expected keys {sorted(REQUIRED_KEYS)}"
                )
            request = row["request"]
            expected = row["expected_task"]
            if not isinstance(request, str) or not request.strip():
                raise DatasetError(f"{path.name}:{line_number}: request must be non-empty")
            if expected not in LABELS:
                raise DatasetError(
                    f"{path.name}:{line_number}: unknown label {expected!r}"
                )
            fingerprint = normalize_text(request)
            if fingerprint in seen:
                raise DatasetError(f"{path.name}:{line_number}: duplicate request")
            seen.add(fingerprint)
            rows.append(row)
    if not rows:
        raise DatasetError(f"{path.name}: dataset is empty")
    return rows


def _per_class_metrics(confusion: dict[str, dict[str, int]]) -> dict[str, dict]:
    """从混淆矩阵计算各类别指标；行是实际标签，列是预测标签。"""
    metrics = {}
    for label in LABELS:
        true_positive = confusion[label][label]
        predicted = sum(confusion[expected][label] for expected in LABELS)
        actual = sum(confusion[label].values())
        precision = true_positive / predicted if predicted else 0.0
        recall = true_positive / actual if actual else 0.0
        f1 = (
            2 * precision * recall / (precision + recall)
            if precision + recall
            else 0.0
        )
        metrics[label] = {
            "precision": round(precision, 4),
            "recall": round(recall, 4),
            "f1": round(f1, 4),
            "support": actual,
        }
    return metrics


def _p95(values: list[float]) -> float:
    """用最近秩法计算第 95 百分位；调用方须保证列表非空。"""
    ordered = sorted(values)
    index = max(0, (95 * len(ordered) + 99) // 100 - 1)
    return ordered[index]


def run_eval(path: Path = DEFAULT_DATASETS[0]) -> dict:
    """评估一个数据集，返回准确率、误触发率、时延及分类明细。"""
    router = RuleBasedRouter()
    rows = load_rows(path)
    stats = DatasetStats()

    for row in rows:
        expected = row["expected_task"]
        started_ns = perf_counter_ns()
        result = router.route(row["request"])
        elapsed_ms = (perf_counter_ns() - started_ns) / 1_000_000
        predicted = result.task_type.value

        stats.total += 1
        stats.latencies_ms.append(elapsed_ms)
        stats.confusion[expected][predicted] += 1
        if expected == "chat":
            stats.chat_support += 1
            if predicted != "chat":
                stats.false_tool_count += 1
        if predicted == expected:
            stats.correct += 1

        bucket = stats.confidence_buckets[_confidence_bucket(result.confidence)]
        bucket[0] += 1
        bucket[1] += int(predicted == expected)

    return {
        "dataset": path.name,
        "router_version": ROUTER_VERSION,
        "total": stats.total,
        "correct": stats.correct,
        "route_accuracy": round(stats.correct / stats.total, 4),
        # 分母是实际为 chat 的样本数；没有该类样本时按 0 报告并同时给出支持数。
        "false_tool_rate": round(
            stats.false_tool_count / stats.chat_support if stats.chat_support else 0.0,
            4,
        ),
        "false_tool_count": stats.false_tool_count,
        "chat_support": stats.chat_support,
        "latency_ms": {
            "mean": round(sum(stats.latencies_ms) / stats.total, 4),
            "p95": round(_p95(stats.latencies_ms), 4),
        },
        "confidence_buckets": {
            label: {
                "count": count,
                "accuracy": round(hits / count, 4) if count else 0.0,
            }
            for label, (count, hits) in stats.confidence_buckets.items()
            if count
        },
        "per_class": _per_class_metrics(stats.confusion),
        "confusion_matrix": stats.confusion,
        "label_counts": dict(Counter(row["expected_task"] for row in rows)),
        "cost_usd": 0.0,
    }


def check_gate(report: dict, thresholds: GateThresholds) -> list[str]:
    """返回所有未达标项；空列表表示通过质量门槛。"""
    violations = []
    if report["route_accuracy"] < thresholds.min_accuracy:
        violations.append(
            f"{report['dataset']}: route_accuracy {report['route_accuracy']} "
            f"< {thresholds.min_accuracy}"
        )
    if report["false_tool_rate"] > thresholds.max_false_tool_rate:
        violations.append(
            f"{report['dataset']}: false_tool_rate {report['false_tool_rate']} "
            f"> {thresholds.max_false_tool_rate}"
        )
    if report["latency_ms"]["p95"] > thresholds.max_p95_latency_ms:
        violations.append(
            f"{report['dataset']}: p95 latency {report['latency_ms']['p95']}ms "
            f"> {thresholds.max_p95_latency_ms}ms"
        )
    return violations


def run_suite(paths: Iterable[Path]) -> dict:
    reports = [run_eval(path) for path in paths]
    return {"reports": reports}


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run router evals and quality gate.")
    parser.add_argument(
        "datasets",
        nargs="*",
        type=Path,
        help="JSONL datasets. Defaults to dev + holdout.",
    )
    parser.add_argument("--min-accuracy", type=float, default=0.90)
    parser.add_argument("--max-false-tool-rate", type=float, default=0.05)
    parser.add_argument("--max-p95-ms", type=float, default=5.0)
    parser.add_argument("--no-gate", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    paths = args.datasets or list(DEFAULT_DATASETS)
    thresholds = GateThresholds(
        min_accuracy=args.min_accuracy,
        max_false_tool_rate=args.max_false_tool_rate,
        max_p95_latency_ms=args.max_p95_ms,
    )

    try:
        reports = [run_eval(path) for path in paths]
    except (DatasetError, OSError) as exc:
        print(f"eval failed: {exc}", file=sys.stderr)
        return 2

    violations = [] if args.no_gate else [
        issue for report in reports for issue in check_gate(report, thresholds)
    ]
    output = {
        "reports": reports,
        "gate": {
            "enabled": not args.no_gate,
            "thresholds": {
                "min_accuracy": thresholds.min_accuracy,
                "max_false_tool_rate": thresholds.max_false_tool_rate,
                "max_p95_latency_ms": thresholds.max_p95_latency_ms,
            },
            "violations": violations,
            "passed": not violations,
        },
    }
    print(json.dumps(output, ensure_ascii=False, indent=2))
    return 0 if not violations else 1


if __name__ == "__main__":
    raise SystemExit(main())
