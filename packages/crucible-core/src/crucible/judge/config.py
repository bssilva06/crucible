from __future__ import annotations

import os
from pathlib import Path

from pydantic import Field, SecretStr

from crucible.domain.base import CrucibleModel


class JudgeConfig(CrucibleModel):
    enabled: bool = True
    provider: str = "gemini"
    model: str = "gemini-2.5-flash"
    timeout_seconds: int = Field(default=30, ge=1)
    default_threshold: float = Field(default=0.7, ge=0, le=1)
    api_key: SecretStr | None = None


def load_judge_config(path: Path) -> JudgeConfig:
    try:
        import yaml
    except ImportError as exc:
        raise RuntimeError("PyYAML is required to load judge config.") from exc

    if path.exists():
        with path.open("r", encoding="utf-8") as handle:
            data = yaml.safe_load(handle) or {}
    else:
        data = {}
    data["api_key"] = _api_key()
    return JudgeConfig.model_validate(data)


def _api_key() -> str | None:
    for name in ("GEMINI_API_KEY", "GOOGLE_API_KEY"):
        value = os.getenv(name)
        if value:
            return value
    return None
