from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any


class ConfigError(RuntimeError):
    """Raised when required Phase 0 configuration is missing."""


@dataclass(frozen=True)
class Phase0Settings:
    env: str
    log_level: str
    provider: str
    b2_application_key_id: str | None
    b2_application_key: str | None
    b2_bucket_name: str | None
    b2_bucket_region: str | None
    b2_endpoint_url: str | None
    b2_object_lock_enabled: bool
    b2_object_lock_mode: str
    b2_object_lock_retention_days: int

    @classmethod
    def from_env(cls) -> "Phase0Settings":
        return cls(
            env=os.getenv("CRUCIBLE_ENV", "local"),
            log_level=os.getenv("CRUCIBLE_LOG_LEVEL", "INFO"),
            provider=os.getenv("CRUCIBLE_PHASE0_PROVIDER", "gmicloud"),
            b2_application_key_id=env_any("B2_APPLICATION_KEY_ID", "B2_KEY_ID"),
            b2_application_key=env_any(
                "B2_APPLICATION_KEY",
                "B2_APP_KEY",
                "B2_APPLICATION_KEY_VALUE",
                "B2_SECRET_KEY",
                "B2_SECRET_ACCESS_KEY",
                "AWS_SECRET_ACCESS_KEY",
            ),
            b2_bucket_name=os.getenv("B2_BUCKET_NAME"),
            b2_bucket_region=os.getenv("B2_BUCKET_REGION"),
            b2_endpoint_url=os.getenv("B2_ENDPOINT_URL"),
            b2_object_lock_enabled=_env_bool("B2_OBJECT_LOCK_ENABLED", default=False),
            b2_object_lock_mode=os.getenv("B2_OBJECT_LOCK_MODE", "governance"),
            b2_object_lock_retention_days=int(os.getenv("B2_OBJECT_LOCK_RETENTION_DAYS", "30")),
        )

    def require_b2(self) -> None:
        missing = [
            name
            for name, value in {
                "B2_APPLICATION_KEY_ID": self.b2_application_key_id,
                "B2_APPLICATION_KEY/B2_APP_KEY": self.b2_application_key,
                "B2_BUCKET_NAME": self.b2_bucket_name,
                "B2_ENDPOINT_URL": self.b2_endpoint_url,
            }.items()
            if not value
        ]
        if missing:
            raise ConfigError(f"Missing required B2 environment variables: {', '.join(missing)}")

    def require_provider_key(self, env_name: str) -> str:
        value = env_any(env_name, *_provider_key_aliases(env_name))
        if not value:
            names = ", ".join((env_name, *_provider_key_aliases(env_name)))
            raise ConfigError(f"Missing required provider environment variable. Checked: {names}")
        return value


def load_yaml(path: Path) -> dict[str, Any]:
    try:
        import yaml
    except ImportError as exc:
        raise ConfigError("PyYAML is required to read configuration files. Install project dependencies.") from exc

    with path.open("r", encoding="utf-8") as handle:
        loaded = yaml.safe_load(handle) or {}
    if not isinstance(loaded, dict):
        raise ConfigError(f"Expected YAML mapping in {path}")
    return loaded


def phase0_provider_config(config_root: Path, provider: str) -> dict[str, Any]:
    models = load_yaml(config_root / "models.yaml")
    providers = models.get("phase0", {}).get("providers", {})
    if provider not in providers:
        raise ConfigError(f"Provider {provider!r} is not configured in configs/models.yaml")
    provider_config = providers[provider]
    if not provider_config.get("enabled", False):
        raise ConfigError(f"Provider {provider!r} is configured but disabled")
    return provider_config


def _env_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def env_any(*names: str) -> str | None:
    for name in names:
        value = os.getenv(name)
        if value:
            return value
    return None


def _provider_key_aliases(env_name: str) -> tuple[str, ...]:
    aliases = {
        "GMICLOUD_API_KEY": ("GMI_API_KEY",),
        "GMI_API_KEY": ("GMICLOUD_API_KEY",),
        "REPLICATE_API_TOKEN": ("REPLICATE_API_KEY",),
        "REPLICATE_API_KEY": ("REPLICATE_API_TOKEN",),
    }
    return aliases.get(env_name, ())
