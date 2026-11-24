"""DeepSeek Chat Completions 适配器（OpenAI 兼容协议）。

产出的 ``complete`` 可直接注入 ``StructuredLLMRouter``：

    from router_lab import StructuredLLMRouter, build_completer

    router = StructuredLLMRouter(build_completer(), model=get_settings().model)
"""

from typing import Callable

from agent_common import Settings, get_settings
from openai import OpenAI

SYSTEM_PROMPT = "You are a precise assistant. Follow the required output format exactly."
MAX_TOKENS = 512


def build_completer(settings: Settings | None = None) -> Callable[[str], str]:
    """返回 ``(prompt: str) -> str``，密钥与模型取自根目录 .env。"""
    settings = settings or get_settings()
    if not settings.is_configured:
        raise RuntimeError("DEEPSEEK_API_KEY 未配置：请在项目根目录 .env 中填写")

    client = OpenAI(api_key=settings.api_key, base_url=settings.base_url)

    def complete(prompt: str) -> str:
        response = client.chat.completions.create(
            model=settings.model,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            temperature=0,
            max_tokens=MAX_TOKENS,
        )
        return response.choices[0].message.content or ""

    return complete
