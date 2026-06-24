from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from crucible.phase0.env import load_dotenv


ROOT = Path(__file__).resolve().parents[4]


@dataclass(frozen=True)
class ApiSettings:
    root: Path
    config_root: Path
    local_storage_root: Path
    cors_origins: list[str]
    dry_run_default: bool
    allow_dry_run: bool
    max_prompt_chars: int

    @classmethod
    def load(cls) -> "ApiSettings":
        load_dotenv(ROOT / ".env")
        return cls(
            root=ROOT,
            config_root=ROOT / "configs",
            local_storage_root=ROOT / "tmp" / "phase0-api-storage",
            cors_origins=_csv_env("CRUCIBLE_API_CORS_ORIGINS", "http://localhost:3000"),
            dry_run_default=_env_bool("CRUCIBLE_API_DRY_RUN_DEFAULT", default=False),
            allow_dry_run=_env_bool("CRUCIBLE_API_ALLOW_DRY_RUN", default=True),
            max_prompt_chars=int(os.getenv("CRUCIBLE_MAX_PROMPT_CHARS", "1200")),
        )


def _env_bool(name: str, *, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _csv_env(name: str, default: str) -> list[str]:
    value = os.getenv(name, default)
    return [part.strip() for part in value.split(",") if part.strip()]
