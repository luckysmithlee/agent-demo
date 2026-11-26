# 结构化 Router 实战（单 Agent 架构）

把用户请求识别为 `chat` / `research` / `coding` 意图，但意图不再用来选择不同 Agent：整个 Lab 只有一个 Agent、一套工具注册表。意图只决定本轮的行为提示和工具能力范围。规则路由是零依赖、可离线评测的主路径；LLM 结构化路由实现同一个 `route()` 接口，可以直接替换。

本实战沿用原文的三类意图和评测指标，将分类结果用于单 Agent 的工具授权。 [结构化 Router 实战 §2.11](https://my.feishu.cn/docx/VytpdGqFGoX0h2xuVPfckjpDnTg#doxcnv8ibL1XgyZyxkbZ0VW1FBf)

## 快速开始

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ../..          # 共享包 agent_common：统一加载根目录 .env
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
├── task_types.py       # TaskType（意图标签）
├── agent.py            # 单 Agent：轮次契约 + 唯一工具注册表 + 能力策略
├── eval_runner.py      # 评测、分层指标、混淆矩阵、门禁 CLI
├── structured_llm.py   # LLM JSON schema 校验、重试、非法输出率
├── llm_client.py       # DeepSeek 补全客户端（OpenAI 兼容，读取根目录 .env）
└── observability.py    # 脱敏路由事件（请求指纹 + 暴露的工具，不含原文）
evals/
├── router_requests.jsonl  # dev 集（调参用）
├── router_holdout.jsonl   # holdout 集（只做验收）
└── run_eval.py
docs/router-design.md    # 设计决策与未决问题
```

## 单 Agent 架构

- **一个入口**：所有请求都走 `SingleAgent.begin()`，没有 chat / research / coding 三套 handler，也没有第二个 Agent。
- **一套工具**：`agent.TOOLS` 是唯一注册表，每个 `ToolSpec` 声明 `side_effects` 与 `network` 能力。
- **一张能力表**：`IntentCapability` 说明某意图允许哪些能力，`ToolScope` 由注册表过滤推导，不手写白名单。
- **运行时再校验**：`call_tool()` 不信任提示词，越权调用直接抛 `ToolNotPermittedError`。

| intent | side effects | network | 本轮可用工具 |
| --- | --- | --- | --- |
| chat | 否 | 否 | 无 |
| research | 否 | 是 | `web_search` |
| coding | 是 | 是 | `shell`, `file_edit`, `run_tests`, `web_search` |

```python
from router_lab import SingleAgent

agent = SingleAgent(executors={"web_search": my_search})
turn = agent.begin("搜索今天最新的 Agent SDK 文章")

print(turn.intent)          # TaskType.RESEARCH
print(turn.scope.tools)     # frozenset({'web_search'})
print(turn.guidance)        # 本轮行为提示，替代原来的 handler prompt

print(agent.call_tool(turn, "web_search", query="agent sdk"))
```

约束：

- chat 的工具集恒为空，保留“闲聊不触发工具副作用”这条安全不变量。
- coding 现在也能 `web_search`：单 Agent 共用一套工具，不再按任务类型拆能力。
- 新增工具只改 `TOOLS` 并确认能力边界，不再新增 handler 表。

`AgentTurn` 字段：`request`、`intent`、`confidence`、`scope`、`guidance`、`reason`、`matched_keywords`、`router_version`、`fallback_recommended`。

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

先跑默认评测，分别查看 30 条开发样本和 25 条留出样本的报告。查看混淆矩阵中 `chat` 行的 `research` 和 `coding` 两列，再把工具误触发率与门禁阈值比较。调整关键词时只看开发集，最后用留出集验收。 [实战验收标准 §2.12](https://my.feishu.cn/docx/VytpdGqFGoX0h2xuVPfckjpDnTg#doxcn1noB50p5T3EDESl3lEc0fd)

- `route_accuracy`：整体准确率。
- `false_tool_rate` 衡量 `chat` 样本被授予工具权限的比例。分母为 `chat` 样本数，分母为零时报告 `0.0`。
- `per_class`：每类 precision / recall / f1 / support。
- `confusion_matrix` 的行是期望标签，列是预测标签。
- `confidence_buckets`：各置信度区间的样本数与准确率，用于检查置信度是否校准。
- `latency_ms.p95` 使用最近秩法。将本地路由耗时从小到大排序，取第 `ceil(0.95 × 样本数)` 项。
- `cost_usd` 在离线规则评测中为 `0.0`。接入真实模型后，按服务端返回的用量和模型单价另行计算费用。

门禁默认值：准确率 ≥ 0.90、false tool rate ≤ 0.05、p95 ≤ 5ms。任一不满足则 CLI 退出码为 1。

```bash
python evals/run_eval.py evals/router_holdout.jsonl \
  --min-accuracy 0.95 --max-false-tool-rate 0.02 --max-p95-ms 2
```

## LLM 结构化路由（替换实现，而非第二个 Agent）

`StructuredLLMRouter` 通过注入的 `complete` 回调调用任意模型：

```python
from router_lab import RuleBasedRouter, SingleAgent, StructuredLLMRouter

router = StructuredLLMRouter(
    complete=my_llm_call,
    model="my-model",
    max_attempts=3,
    fallback=RuleBasedRouter(),
)
agent = SingleAgent(router=router)      # 只影响意图判断，不切换 Agent

turn = agent.begin("帮我排查线上接口 500")
print(turn.intent, turn.confidence)
print(router.stats()["invalid_output_rate"])
```

- 输出必须是单个 JSON 对象，字段 `task_type` / `confidence` / `reason`，拒绝额外字段。
- 校验失败默认最多尝试 3 次。配置 `fallback` 后，重试耗尽、模型调用超时，或模型置信度低于规则配置的 `confidence_threshold`（默认 `0.70`）时，由规则路由决定意图和工具范围。未配置规则回退时，重试耗尽和超时分别抛出 `InvalidRouteDecision` 和 `TimeoutError`。
- 记录 `invalid_output_rate`，作为接入真实模型后的核心质量指标。
- Prompt 把用户请求放在 `<request>` 标签内并声明为不可信数据，降低提示注入风险。
- DeepSeek 适配器使用 `temperature=0`，给单次 SDK 请求配置 10 秒超时。回退后，`router_version` 记录实际产出结论的规则版本。
- 任何实现 `route(request) -> RouteResult` 的对象都能注入 `SingleAgent`。

## 开发说明

- 关键词只改 `src/router_lab/rules.py`，并同步更新 `ROUTER_VERSION`。
- 调参只使用 `evals/router_requests.jsonl`；`router_holdout.jsonl` 只用于验收，禁止针对它改关键词。
- 新增工具只改 `agent.TOOLS`，能力边界在 `CAPABILITIES` 确认；不要重新引入按任务类型的 handler 表。
- 提交前运行 `pytest -q` 与 `python evals/run_eval.py`。
