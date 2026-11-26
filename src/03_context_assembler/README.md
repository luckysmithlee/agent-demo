# context-assembler

Context Assembler（由 `agent_common/template` 复制而来）。

## 快速开始

```bash
cd src/03_context_assembler
python -m venv .venv
source .venv/bin/activate
pip install -e ../..          # 共享包 agent_common
pip install -e ".[dev]"
pytest tests/
```

约定：

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
