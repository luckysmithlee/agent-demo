"""读取项目根目录 .env，供所有 Lab 共用。"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

# agent_common/env.py -> 项目根目录
ENV_FILE = Path(__file__).resolve().parents[1] / ".env"

_loaded = False


def load_env(path: Path | None = None) -> Path:
    """把 .env 载入当前进程环境，重复调用只生效一次。

    已存在的系统环境变量优先（override=False），方便部署时用平台变量覆盖。
    文件不存在时静默跳过，也会标记为已加载；后续传入其他路径不会重新加载。
    返回本次指定的路径（默认项目根目录的 .env），不代表该文件已被读取。
    """
    global _loaded
    target = path or ENV_FILE
    if not _loaded:
        load_dotenv(target)
        _loaded = True
    return target


@dataclass(frozen=True)
class Settings:
    """一次读取所得的不可变配置快照；空 API key 表示尚未配置。"""

    api_key: str
    base_url: str
    model: str
    app_env: str
    log_level: str

    @property
    def is_configured(self) -> bool:
        """仅检查 API key 是否非空，不验证密钥是否有效。"""
        return bool(self.api_key)


def get_settings() -> Settings:
    """先尝试加载 .env，再从当前进程环境生成配置快照。

    每次调用都会重新读取环境变量；缺失时使用下方默认值。
    """
    load_env()
    return Settings(
        api_key=os.getenv("DEEPSEEK_API_KEY", "").strip(),
        base_url=os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com").strip(),
        model=os.getenv("DEEPSEEK_MODEL", "deepseek-v4.1-flash").strip(),
        app_env=os.getenv("APP_ENV", "development"),
        log_level=os.getenv("LOG_LEVEL", "INFO").upper(),
    )
