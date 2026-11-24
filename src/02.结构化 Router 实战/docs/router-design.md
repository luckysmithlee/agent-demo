# Router 设计决策

## 背景

Agent 入口需要一个低延迟、可解释、可回归的请求分类器，把请求路由到 chat / research / coding，并决定是否允许工具调用。规则路由器是第一版基线；LLM 结构化路由只作为低置信度兜底。

## 决策

### 1. 加权关键词评分，而不是首次命中

早期实现按顺序判断，coding 命中一个词就返回，导致“找出 PostgreSQL 最近版本修复的安全漏洞摘要”被误判为 coding。现在分别给 coding / research 计分，按总分比较。

### 2. 强/弱权重

- 强关键词（2 分）：语义明确，如“修复”“调研”“最新”。
- 弱关键词（1 分）：单独出现有歧义，如“查找”“接口”“比较”“更新”。

`min_score=2`，弱关键词必须组合成双证据才能改变路由结果；单弱证据默认 chat。这优先保护 false tool rate：chat 误触发工具比 research/coding 误判更危险。

### 3. 文本归一化

- NFKC：全角字符（如 `ｒｅａｃｔ`）转半角。
- 小写 + 空白压缩。
- ASCII 关键词使用词边界正则，避免 `code` 命中 `barcode`、`fix` 命中 `prefix`。
- 中文关键词仍用子串匹配，因为中文无空格分词；歧义由权重和 `min_score` 吸收。

### 4. 置信度与兜底

- 有判定：`0.60 + 0.06 * score + min(0.12, 0.03 * margin)`，上限 0.98。
- 弱证据：chat 0.55；无证据：chat 0.50；平票：chat 0.55。
- `fallback_recommended = confidence < 0.70`。上层可以把这类请求升级到 `StructuredLLMRouter` 或反问用户。
- 置信度公式尚未做概率校准，`confidence_buckets` 指标用于持续检查。

### 5. 版本化

关键词表与版本号在 `src/router_lab/rules.py`。`RouteResult.router_version` 写入每次结果，评测报告也带版本，保证结果可追溯。改关键词必须提升版本号。

### 6. LLM 结构化输出

- Pydantic 模型严格校验：`task_type` 枚举、`confidence` 在 [0,1]、`reason` 非空且 ≤ 500 字符、禁止额外字段。
- 非法输出自动重试，默认 3 次；记录 `invalid_output_rate`。
- 请求包裹在 `<request>` 标签内并声明为不可信数据；模型输出不做自由文本拼接。
- 生产接入建议 `temperature=0`、固定模型版本；全部重试失败时回退规则路由。

### 7. 评测与过拟合控制

- dev 集用于调词，holdout 集只验收。
- `false_tool_rate` 分母必须是 chat 样本数，不能用全量样本数稀释。
- 除整体准确率外，报告每类 P/R/F1、混淆矩阵、置信度分桶。
- CI 门禁：准确率 ≥ 0.90、false tool rate ≤ 0.05、p95 ≤ 5ms。

### 8. 工具白名单

`dispatch.py` 把任务类型映射到 handler 和允许的工具。chat 的工具集为空；即使路由给出高置信度，chat 也不能触发工具。

## 未决问题

- **置信度校准**：当前公式是启发式，需要更大数据集做分桶校准或等渗回归。
- **多意图请求**：“搜索并修复”同时含 research 和 coding，当前返回单一主标签；可扩展 `secondary_task_types`。
- **真实成本核算**：规则路由 `cost_usd=0`；接入 LLM 后需要按 token 记录成本。
- **生产日志落点**：`observability.RouteEvent` 已脱敏，但尚未接入实际日志/追踪后端。
- **长尾词表维护**：关键词仍是手工维护，后续可考虑从误判样本挖掘候选词，但需保持 holdout 隔离。
