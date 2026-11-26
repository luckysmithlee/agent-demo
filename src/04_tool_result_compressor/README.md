# tool-result-compressor

对文本形式的 Tool Result 控制字符预算。短结果原样返回；超出预算时保留首尾，插入包含原文字符数的截断标记。结果总长度不超过 `max_chars`，首尾各至少保留一个字符；预算不足以容纳标记和首尾字符时抛出 `ValueError`。空字符串有效，预算必须是正整数。

这是有损截断，中间的错误详情、结构化数据或其他重要信息可能丢失；它不保证 JSON 等格式仍然有效，也不防止工具结果中的提示注入。预算使用 Python 字符数，并非模型 Token 数。

## 使用

```python
from tool_result_compressor import compress_tool_result

result = compress_tool_result("工具输出...", max_chars=1000)
```

## 练习：保留测试失败证据

测试日志的关键错误可能夹在大量正常输出中。`compact_test_output` 按 stdout、stderr 的顺序扫描，统计含 `FAILED` 或 `ERROR` 的行，保留前 50 条命中行和末尾 80 行。 [Tool Result 压缩实战 §3.10](https://my.feishu.cn/docx/VytpdGqFGoX0h2xuVPfckjpDnTg#doxcn17GsFleChsMu8fxwd6iwJf)

```python
from tool_result_compressor import compact_test_output

failure = "FAILED tests/test_config.py::test_missing_key"
stdout = "\n".join(["INFO 检查配置"] * 90 + [failure] + ["INFO 清理测试数据"] * 90)
stderr = "ERROR 配置缺少必填项"

summary = compact_test_output(stdout, stderr)
assert summary["failure_count"] == 2
assert summary["important_lines"] == [failure, stderr]
assert failure not in summary["tail"]
```

`failure_count` 统计命中行，同一次失败的多行日志可能分别计数。摘要按行数限制保留范围，单行很长时仍需要按上下文预算取舍。可以把所需命中行作为下一步的工具片段传入上下文组装器。 [上下文组装实战](../03_context_assembler/README.md)

## 设计与离线评测

设计文档说明字符预算、日志命中口径，以及组装上下文前怎样选择压缩方式。 [工具结果压缩设计](docs/compression-design.md)

在 Lab 目录运行以下命令，验收短结果原样保留、长结果首尾截断、跨输出流提取错误和保留尾部之外的错误。任一案例未通过时，报告会列出失败字段并返回退出码 `1`。 [评测数据](evals/compression_cases.jsonl)

```bash
PYTHONPATH=src python evals/run_eval.py
```

## 测试

```bash
cd src/04_tool_result_compressor
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
pytest tests/
```
