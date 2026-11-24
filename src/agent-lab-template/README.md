# agent-lab

一个用于实验和迭代 AI Agent 能力的本地项目。

## 目录结构

```
agent-lab/
├── README.md        # 项目说明
├── .env.example    # 环境变量示例（复制为 .env 后填写）
├── pyproject.toml  # Python 项目与依赖配置
├── src/             # 源码
├── tests/           # 单元测试
├── evals/           # 评测集与评测脚本
└── docs/            # 设计文档与笔记
```

## 快速开始

```bash
# 1. 安装依赖（建议先创建虚拟环境）
python -m venv .venv
source .venv/bin/activate
pip install -e .

# 2. 配置环境变量
cp .env.example .env

# 3. 运行测试
pytest tests/
```

## 开发说明

- 源码放在 `..` 下；
- 单元测试放在 `tests`，随代码一起迭代；
- 效果评测数据、Prompt 与评测脚本放在 `evals`；
- 架构设计、决策记录等文档放在 `docs`。
