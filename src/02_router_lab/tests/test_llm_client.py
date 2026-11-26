import json
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from openai import APITimeoutError

from agent_common import Settings
from router_lab import llm_client
from router_lab.llm_client import build_completer
from router_lab.structured_llm import StructuredLLMRouter
from router_lab.task_types import TaskType


def settings(**overrides):
    values = {
        "api_key": "test-key",
        "base_url": "https://api.example.test",
        "model": "deepseek-v4.1-flash",
        "app_env": "test",
        "log_level": "INFO",
    }
    values.update(overrides)
    return Settings(**values)


def fake_openai(monkeypatch, content: str | None, *, error: APITimeoutError | None = None):
    calls: dict = {}

    class FakeCompletions:
        def create(self, **kwargs):
            calls["request"] = kwargs
            if error is not None:
                raise error
            message = SimpleNamespace(content=content)
            return SimpleNamespace(choices=[SimpleNamespace(message=message)])

    class FakeClient:
        def __init__(self, **kwargs):
            calls["client"] = kwargs
            self.chat = SimpleNamespace(completions=FakeCompletions())

    monkeypatch.setattr(llm_client, "OpenAI", FakeClient)
    return calls


def valid_output(**overrides):
    payload = {"task_type": "chat", "confidence": 0.88, "reason": "explains a concept"}
    payload.update(overrides)
    return json.dumps(payload)


def test_requires_api_key():
    with pytest.raises(RuntimeError, match="DEEPSEEK_API_KEY"):
        build_completer(settings(api_key=""))


def test_forwards_prompt_and_returns_text(monkeypatch):
    calls = fake_openai(monkeypatch, valid_output())

    complete = build_completer(settings())

    assert complete("怎么理解向量检索？") == valid_output()
    assert calls["client"]["api_key"] == "test-key"
    assert calls["client"]["base_url"] == "https://api.example.test"
    assert calls["client"]["timeout"] == 10.0
    assert calls["client"]["max_retries"] == 0
    assert calls["request"]["model"] == "deepseek-v4.1-flash"
    assert calls["request"]["temperature"] == 0
    assert calls["request"]["messages"][-1] == {
        "role": "user",
        "content": "怎么理解向量检索？",
    }


def test_timeout_is_translated_for_router(monkeypatch):
    error = APITimeoutError(request=Mock())
    fake_openai(monkeypatch, None, error=error)

    with pytest.raises(TimeoutError, match="DeepSeek 模型请求超时") as exc:
        build_completer(settings())("解释一下什么是 RAG")

    assert exc.value.__cause__ is error


def test_none_content_becomes_empty_string(monkeypatch):
    fake_openai(monkeypatch, None)

    assert build_completer(settings())("hi") == ""


def test_completer_drives_structured_router(monkeypatch):
    fake_openai(monkeypatch, valid_output())

    router = StructuredLLMRouter(build_completer(settings()), model="deepseek-v4.1-flash")
    result = router.route("解释一下什么是 RAG")

    assert result.task_type is TaskType.CHAT
    assert result.confidence == 0.88
    assert result.router_version.startswith("llm:deepseek-v4.1-flash@")
