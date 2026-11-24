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
    文件不存在时静默跳过，不会报错。
    """
    global _loaded
    target = path or ENV_FILE
    if not _loaded:
        load_dotenv(target)
        _loaded = True
    return target


@dataclass(frozen=True)
class Settings:
    api_key: str
    base_url: str
    model: str
    app_env: str
    log_level: str

    @property
    def is_configured(self) -> bool:
        return bool(self.api_key)


def get_settings() -> Settings:
    load_env()
    return Settings(
        api_key=os.getenv("DEEPSEEK_API_KEY", "").strip(),
        base_url=os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com").strip(),
        model=os.getenv("DEEPSEEK_MODEL", "deepseek-v4.1-flash").strip(),
        app_env=os.getenv("APP_ENV", "development"),
        log_level=os.getenv("LOG_LEVEL", "INFO").upper(),
    )
