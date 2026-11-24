"""跨 Lab 共享的环境变量加载入口。

用法：
    from agent_common import get_settings

    settings = get_settings()
    settings.api_key   # DEEPSEEK_API_KEY
"""

from .env import ENV_FILE, Settings, get_settings, load_env

__all__ = ["ENV_FILE", "Settings", "get_settings", "load_env"]
