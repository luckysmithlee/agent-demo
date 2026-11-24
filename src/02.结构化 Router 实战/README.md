# 结构化 Router 实战

把用户请求结构化分类为 `chat` / `research` / `coding`，为后续 Agent 分派和工具白名单提供依据。当前主线是零依赖、可离线评测的规则路由器，LLM 结构化路由作为低置信度兜底路径。

## 快速开始

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"

pytest -q
python evals/run_eval.py
```

`python evals/run_eval.py` 直接运行即可，无需先安装包；它会评测 dev + holdout 两个数据集，并执行质量门禁。

## 目录

```
src/router_lab/
├── router.py           # 规则路由：归一化、评分、置信度、低置信兜底标记
├── rules.py            # 版本化关键词表与权重
├── task_types.py       # TaskType 枚举
├── eval_runner.py      # 评测、分层指标、混淆矩阵、门禁 CLI
├── structured_llm.py   # LLM JSON schema 校验、重试、非法输出率
├── dispatch.py         # TaskType -> handler / 工具白名单
└── observability.py    # 脱敏路由事件（请求指纹，不含原文）
evals/
├── router_requests.jsonl  # dev 集（调参用）
├── router_holdout.jsonl   # holdout 集（只做验收）
└── run_eval.py
docs/router-design.md    # 设计决策与未决问题
```

## 路由器行为

- **归一化**：NFKC（全角转半角）、小写、压缩空白。
- **匹配**：中文关键词用子串；ASCII 关键词用词边界正则，`code` 不会命中 `barcode`。
- **评分**：关键词分强（2 分）/ 弱（1 分）。`min_score=2` 才判定任务类型。
- **优先级**：按总分比较，不再“coding 命中即返回”。
- **置信度**：`0.60 + 0.06 * score + margin`，上限 0.98；弱证据兜底 chat 为 0.55，无证据为 0.50。
- **平票/弱证据**：默认 `chat`，并置 `fallback_recommended=True`，由上层升级到 LLM 或追问。
- **可复现**：`RouteResult.router_version` 来自 `rules.ROUTER_VERSION`。

`RouteResult` 字段：`task_type`、`confidence`、`reason`、`matched_keywords`、`router_version`、`fallback_recommended`。

## 评测指标

- `route_accuracy`：整体准确率。
- `false_tool_rate`：**分母是 chat 样本数**，衡量 chat 被误路由到需要工具的任务的比例。
- `per_class`：每类 precision / recall / f1 / support。
- `confusion_matrix`：期望标签 x 预测标签。
- `confidence_buckets`：各置信度区间的样本数与准确率，用于检查置信度是否校准。
- `latency_ms.p95`：规则路由本地延迟。

门禁默认值：准确率 ≥ 0.90、false tool rate ≤ 0.05、p95 ≤ 5ms。任一不满足则 CLI 退出码为 1。

```bash
python evals/run_eval.py evals/router_holdout.jsonl \
  --min-accuracy 0.95 --max-false-tool-rate 0.02 --max-p95-ms 2
```

## LLM 结构化路由（兜底）

`StructuredLLMRouter` 通过注入的 `complete` 回调调用任意模型：

```python
from router_lab import StructuredLLMRouter

router = StructuredLLMRouter(complete=my_llm_call, model="my-model", max_attempts=3)
result = router.route("帮我排查线上接口 500")
print(result.task_type, result.confidence)
print(router.stats()["invalid_output_rate"])
```

- 输出必须是单个 JSON 对象，字段 `task_type` / `confidence` / `reason`，拒绝额外字段。
- 校验失败自动重试，最多 3 次；仍失败抛 `InvalidRouteDecision`。
- 记录 `invalid_output_rate`，作为接入真实模型后的核心质量指标。
- Prompt 把用户请求放在 `<request>` 标签内并声明为不可信数据，降低提示注入风险。
- 生产接入时建议 `temperature=0`、固定模型版本，并在低置信/失败时回退规则路由。

## 分派与工具白名单

`router_lab.dispatch` 定义任务类型到 handler 的契约：

| TaskType | allowed_tools |
| --- | --- |
| chat | 无 |
| research | `web_search` |
| coding | `shell`, `file_edit`, `run_tests` |

chat 永不带工具，避免规则误判造成工具副作用。

## 开发说明

- 关键词只改 `src/router_lab/rules.py`，并同步更新 `ROUTER_VERSION`。
- 调参只使用 `evals/router_requests.jsonl`；`router_holdout.jsonl` 只用于验收，禁止针对它改关键词。
- 提交前运行 `pytest -q` 与 `python evals/run_eval.py`。
