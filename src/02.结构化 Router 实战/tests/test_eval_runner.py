import json

import pytest

from router_lab.eval_runner import (
    DEFAULT_DATASETS,
    DatasetError,
    GateThresholds,
    check_gate,
    load_rows,
    main,
    run_eval,
)


def write_jsonl(path, rows):
    path.write_text(
        "\n".join(json.dumps(row, ensure_ascii=False) for row in rows) + "\n",
        encoding="utf-8",
    )
    return path


def test_default_datasets_pass_the_gate():
    thresholds = GateThresholds()
    for path in DEFAULT_DATASETS:
        assert path.exists(), f"missing dataset: {path}"
        report = run_eval(path)
        assert check_gate(report, thresholds) == []
        assert report["route_accuracy"] >= thresholds.min_accuracy


def test_report_has_layered_metrics():
    report = run_eval(DEFAULT_DATASETS[0])

    assert set(report["confusion_matrix"]) == {"chat", "research", "coding"}
    assert set(report["per_class"]) == {"chat", "research", "coding"}
    for label, metrics in report["per_class"].items():
        assert 0.0 <= metrics["precision"] <= 1.0
        assert 0.0 <= metrics["recall"] <= 1.0
        assert 0.0 <= metrics["f1"] <= 1.0
        assert metrics["support"] == report["label_counts"][label]

    bucket_counts = sum(
        bucket["count"] for bucket in report["confidence_buckets"].values()
    )
    assert bucket_counts == report["total"]


def test_confusion_matrix_totals_match_dataset():
    report = run_eval(DEFAULT_DATASETS[0])
    matrix_total = sum(
        count
        for row in report["confusion_matrix"].values()
        for count in row.values()
    )

    assert matrix_total == report["total"]


def test_false_tool_rate_uses_chat_denominator(tmp_path):
    dataset = write_jsonl(
        tmp_path / "small.jsonl",
        [
            {"request": "修复这个 bug", "expected_task": "chat"},
            {"request": "修复这个 bug", "expected_task": "coding"},
        ],
    )

    with pytest.raises(DatasetError, match="duplicate"):
        load_rows(dataset)

    dataset = write_jsonl(
        tmp_path / "small.jsonl",
        [
            {"request": "修复这个 bug", "expected_task": "chat"},
            {"request": "实现新的接口", "expected_task": "coding"},
        ],
    )
    report = run_eval(dataset)

    assert report["chat_support"] == 1
    assert report["false_tool_count"] == 1
    assert report["false_tool_rate"] == 1.0


@pytest.mark.parametrize(
    "rows",
    [
        [{"request": "解释 TCP", "expected_task": "unknown"}],
        [{"request": "解释 TCP"}],
        [{"request": "", "expected_task": "chat"}],
        [{"request": "解释 TCP", "expected_task": "chat", "extra": 1}],
        [],
    ],
)
def test_dataset_validation_rejects_bad_rows(tmp_path, rows):
    dataset = write_jsonl(tmp_path / "bad.jsonl", rows)

    with pytest.raises(DatasetError):
        load_rows(dataset)


def test_dataset_validation_rejects_bad_json(tmp_path):
    dataset = tmp_path / "bad.jsonl"
    dataset.write_text("{not json}\n", encoding="utf-8")

    with pytest.raises(DatasetError, match="invalid JSON"):
        load_rows(dataset)


def test_gate_reports_each_violation():
    report = {
        "dataset": "x.jsonl",
        "route_accuracy": 0.5,
        "false_tool_rate": 0.5,
        "latency_ms": {"p95": 100.0},
    }
    violations = check_gate(report, GateThresholds())

    assert len(violations) == 3


def test_gate_thresholds_validate_ranges():
    with pytest.raises(ValueError):
        GateThresholds(min_accuracy=1.5)
    with pytest.raises(ValueError):
        GateThresholds(max_p95_latency_ms=0)


def test_cli_passes_on_holdout(capsys):
    exit_code = main([str(DEFAULT_DATASETS[1])])

    output = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert output["gate"]["passed"] is True
    assert output["reports"][0]["route_accuracy"] >= 0.90


def test_cli_fails_gate_on_impossible_threshold(capsys):
    exit_code = main([str(DEFAULT_DATASETS[0]), "--max-p95-ms", "0.0001"])

    output = json.loads(capsys.readouterr().out)
    assert exit_code == 1
    assert output["gate"]["passed"] is False
