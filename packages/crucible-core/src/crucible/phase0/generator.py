from __future__ import annotations

import base64
from dataclasses import dataclass
from typing import Any

from crucible.phase0.brief import Brief
from crucible.phase0.config import ConfigError, Phase0Settings


@dataclass(frozen=True)
class GeneratedAsset:
    data: bytes
    mime_type: str
    model: str
    provider: str
    genblaze_metadata: dict[str, Any]


class Generator:
    def generate(self, brief: Brief) -> GeneratedAsset:
        raise NotImplementedError


class DryRunGenerator(Generator):
    """Deterministic fake image generator for no-network smoke tests."""

    _ONE_BY_ONE_PNG = base64.b64decode(
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMB/atv"
        "pU8AAAAASUVORK5CYII="
    )

    def generate(self, brief: Brief) -> GeneratedAsset:
        return GeneratedAsset(
            data=self._ONE_BY_ONE_PNG,
            mime_type="image/png",
            model="dry-run-1x1-png",
            provider="dry-run",
            genblaze_metadata={
                "mode": "dry_run",
                "brief_id": brief.brief_id,
                "note": "No provider call was made.",
            },
        )


class GenblazeGenerator(Generator):
    """Thin live adapter for Phase 0.

    Genblaze is still isolated here so SDK surface changes do not leak into the
    rest of the Phase 0 spine.
    """

    def __init__(self, settings: Phase0Settings, provider_config: dict[str, Any]) -> None:
        self.settings = settings
        self.provider = settings.provider
        self.model = str(provider_config["model"])
        self.api_key_env = str(provider_config["api_key_env"])
        settings.require_provider_key(self.api_key_env)

    def generate(self, brief: Brief) -> GeneratedAsset:
        try:
            import genblaze  # type: ignore[import-not-found]
        except ImportError as exc:
            raise ConfigError(
                "Genblaze is required for live generation. Install the Genblaze core and provider adapter packages."
            ) from exc

        if hasattr(genblaze, "Pipeline"):
            return self._generate_with_pipeline(genblaze, brief)

        raise ConfigError(
            "Installed Genblaze package does not expose a recognized Phase 0 generation API. "
            "Update crucible.phase0.generator.GenblazeGenerator for the installed SDK version."
        )

    def _generate_with_pipeline(self, genblaze_module: Any, brief: Brief) -> GeneratedAsset:
        pipeline = genblaze_module.Pipeline(model=self.model)
        result = pipeline.run(brief.prompt)
        data = _extract_bytes(result)
        metadata = _extract_metadata(result)
        return GeneratedAsset(
            data=data,
            mime_type=metadata.pop("mime_type", "image/png"),
            model=self.model,
            provider=self.provider,
            genblaze_metadata=metadata,
        )


def _extract_bytes(result: Any) -> bytes:
    for attr in ("bytes", "data", "content"):
        value = getattr(result, attr, None)
        if isinstance(value, bytes):
            return value

    if isinstance(result, bytes):
        return result

    if isinstance(result, dict):
        for key in ("bytes", "data", "content"):
            value = result.get(key)
            if isinstance(value, bytes):
                return value

    raise ConfigError("Could not extract image bytes from Genblaze result.")


def _extract_metadata(result: Any) -> dict[str, Any]:
    if isinstance(result, dict):
        return {key: value for key, value in result.items() if key not in {"bytes", "data", "content"}}

    metadata = getattr(result, "metadata", None)
    if isinstance(metadata, dict):
        return dict(metadata)

    return {"result_type": type(result).__name__}
