# context-assembler

将指令、当前请求和可选片段组装为结构化上下文，并控制字符预算。

指令和请求必须非空且完整保留，超出预算时会报错。可选片段按传入顺序从高到低尝试加入。用 `ContextFragment(content, max_chars)` 为单段指定正整数限额，超限时保留开头并在限额内加上 `…`。普通字符串保持原样。应用单段限额后，仍放不下的片段整段跳过，再继续尝试后续片段。

预算按保留字符串的 Python 字符长度之和计算，不含调用方后续添加的分隔符或其他格式，也不等同于模型的 Token 数。

结果包含已用字符数、总预算和收录的片段。`skipped_indices` 记录跳过片段的原始索引，`truncated_indices` 记录收录片段中被截断的原始索引。 [Context Assembler 实战 §3.9](https://my.feishu.cn/docx/VytpdGqFGoX0h2xuVPfckjpDnTg#doxcn8iv2vBxcylh6TEIQLo3OGc)

## 快速开始

```bash
cd src/03_context_assembler
python -m venv .venv
source .venv/bin/activate
pip install -e ../..          # 共享包 agent_common
pip install -e ".[dev]"
pytest tests/
```

## 使用示例

```python
from context_assembler import assemble_context

context = assemble_context(
    instructions="你是助手",
    request="你好",
    fragments=["背景资料", "补充"],
    max_chars=8,
)
assert context.fragments == ("补充",)
assert context.skipped_indices == (0,)
assert context.used_chars == 8
```

## 练习：组装一次测试排查的上下文

将稳定规则放进 `instructions`，将当前会话目标放进 `request`。近期会话、按需检索资料和本轮工具结果作为可选片段，按当前任务的重要性排列。本例先限定工具结果的长度，保留错误摘要，随后按总预算收录近期会话和截断后的工具结果。 [上下文四层 §3.4](https://my.feishu.cn/docx/VytpdGqFGoX0h2xuVPfckjpDnTg#doxcnHWq52AzzfygN2bQlSDua7N)

```python
from context_assembler import ContextFragment, assemble_context

instructions = "根据证据回答。"
request = "请排查测试失败。"
history = "近期会话：本轮只诊断。"
error_summary = "工具摘要：ERROR 缺少配置"
tool_result = ContextFragment(f"{error_summary}，请检查环境变量。", len(error_summary) + 1)
fragments = [history, tool_result, "检索资料：项目配置说明。"]
budget = len(instructions) + len(request) + len(history) + tool_result.max_chars

context = assemble_context(instructions, request, fragments, max_chars=budget)
assert context.fragments == (history, f"{error_summary}…")
assert context.skipped_indices == (2,)
assert context.truncated_indices == (1,)
assert context.used_chars == budget
```

把预算缩到刚好容纳规则和请求，再检查 `skipped_indices` 是否变为 `(0, 1, 2)`。实际排查时，检查最终发送给模型的规则和请求是否完整、被跳过的片段是否包含关键证据，以及外部内容是否夹带指令。 [Context Debugging 清单 §3.11](https://my.feishu.cn/docx/VytpdGqFGoX0h2xuVPfckjpDnTg#doxcnDVuA5588PRriCu9z5MGfrd)

向组装器传入工具结果前，可先提取相关证据并控制单段长度。 [工具结果压缩实战](../04_tool_result_compressor/README.md)

## 设计与离线评测

设计文档记录上下文分层、预算决策和定位片段丢失的方法。 [上下文组装设计](docs/context-design.md)

在 Lab 目录运行以下命令，核对构建失败、场地更新、紧预算摘要和部署排查四个场景。输出按案例列出不符预期的字段，任一案例未通过时退出码为 `1`。 [评测数据](evals/context_cases.jsonl)

```bash
PYTHONPATH=src python evals/run_eval.py
```

## 环境约定

- 每个 Lab 使用自己的 `.venv`；根目录 `.venv` 只用于 IDE 解析和当前在做的 Lab
- 环境变量统一放在仓库根目录 `.env`，由 `agent_common` 加载，不要在 Lab 内新建

## 目录结构

```
context-assembler/
├── README.md
├── pyproject.toml
├── src/context_assembler/   # 源码包
├── tests/               # 单元测试
├── evals/               # 评测集与评测脚本
└── docs/                # 设计文档与笔记
```

## 开发说明

- 源码放在 `src/` 下；
- 单元测试放在 `tests`，随代码一起迭代；
- 效果评测数据、Prompt 与评测脚本放在 `evals`；
- 架构设计、决策记录等文档放在 `docs`。
