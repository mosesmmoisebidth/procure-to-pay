import os
from pathlib import Path
from typing import Iterable, List


def env(key: str, default: str | None = None) -> str | None:
    return os.getenv(key, default)


def env_bool(key: str, default: bool = False) -> bool:
    value = os.getenv(key)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def env_list(key: str, default: Iterable[str] | None = None) -> List[str]:
    value = os.getenv(key)
    if not value:
        return list(default or [])
    return [item.strip() for item in value.split(",") if item.strip()]


def env_path(key: str, default: str | Path | None = None) -> Path:
    value = os.getenv(key)
    if value:
        return Path(value)
    if default is None:
        raise ValueError(f"Environment variable '{key}' is required")
    return Path(default)
