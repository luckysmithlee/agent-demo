"""DeepSeek Chat Completions 适配器（OpenAI 兼容协议）。

产出的 ``complete`` 可直接注入 ``StructuredLLMRouter``：

    from router_lab import StructuredLLMRouter, build_completer

    router = StructuredLLMRouter(build_completer(), model=get_settings().model)
"""

from typing import Callable

from agent_common import Settings, get_settings
from openai import APITimeoutError, OpenAI

SYSTEM_PROMPT = "You are a precise assistant. Follow the required output format exactly."
MAX_TOKENS = 512


def build_completer(settings: Settings | None = None) -> Callable[[str], str]:
    """创建模型调用函数，未传配置时读取默认设置。

    缺少密钥时抛出 RuntimeError，模型请求超时时抛出 TimeoutError。
    """
    settings = settings or get_settings()
    if not settings.is_configured:
        raise RuntimeError("DEEPSEEK_API_KEY 未配置：请在项目根目录 .env 中填写")

    # 关闭 SDK 重试，让路由层在首次超时后即可决定是否降级。
    client = OpenAI(api_key=settings.api_key, base_url=settings.base_url, timeout=10.0, max_retries=0)

    def complete(prompt: str) -> str:
        try:
            response = client.chat.completions.create(
                model=settings.model,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": prompt},
                ],
                temperature=0,
                max_tokens=MAX_TOKENS,
            )
        except APITimeoutError as exc:
            raise TimeoutError("DeepSeek 模型请求超时") from exc
        return response.choices[0].message.content or ""

    return complete
