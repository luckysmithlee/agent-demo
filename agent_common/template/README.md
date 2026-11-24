# agent-lab

AI Agent 实践的项目模板。后续每个实践都从本模板复制一份，再按需修改。

## 从模板创建新 Lab

在仓库根目录执行：

```bash
cp -r agent_common/template src/03_xxx_lab
```

复制后改三处，保证包名唯一、能独立安装：

1. 目录名：`03_xxx_lab` 按顺序编号，模板本身不编号
2. `pyproject.toml` 的 `name`：`agent-lab` → `xxx-lab`
3. 源码包目录：`src/agent_lab/` → `src/xxx/`

约定：

- 每个 Lab 使用自己的 `.venv`；根目录 `.venv` 只用于 IDE 解析和当前在做的 Lab
- 环境变量统一放在仓库根目录 `.env`，由 `agent_common` 加载，不要在 Lab 内新建

## 快速开始

```bash
cd src/03_xxx_lab
python -m venv .venv
source .venv/bin/activate
pip install -e ../..          # 共享包 agent_common
pip install -e ".[dev]"
pytest tests/
```

## 目录结构

```
agent-lab/
├── README.md
├── pyproject.toml
├── src/agent_lab/   # 源码包（复制后改名）
├── tests/           # 单元测试
├── evals/           # 评测集与评测脚本
└── docs/            # 设计文档与笔记
```

## 开发说明

- 源码放在 `src/` 下；
- 单元测试放在 `tests`，随代码一起迭代；
- 效果评测数据、Prompt 与评测脚本放在 `evals`；
- 架构设计、决策记录等文档放在 `docs`。
