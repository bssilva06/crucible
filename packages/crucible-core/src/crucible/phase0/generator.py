from __future__ import annotations

import base64
from dataclasses import dataclass
from pathlib import Path
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
        self.api_key = settings.require_provider_key(self.api_key_env)

    def generate(self, brief: Brief) -> GeneratedAsset:
        try:
            from genblaze_core import Modality, Pipeline  # type: ignore[import-not-found]
        except ImportError as exc:
            raise ConfigError(
                "Genblaze is required for live generation. Install the Genblaze core and provider adapter packages."
            ) from exc

        provider = self._provider()
        result = (
            Pipeline("crucible-phase0")
            .step(
                provider,
                model=self.model,
                prompt=brief.prompt,
                modality=Modality.IMAGE,
            )
            .run(timeout=600)
        )
        return self._from_genblaze_result(result)

    def _provider(self) -> Any:
        if self.provider == "gmicloud":
            try:
                from genblaze_gmicloud import GMICloudImageProvider  # type: ignore[import-not-found]
            except ImportError as exc:
                raise ConfigError("Install genblaze-gmicloud for the configured GMICloud provider.") from exc
            return GMICloudImageProvider(api_key=self.api_key)

        if self.provider == "replicate":
            try:
                from genblaze_replicate import ReplicateProvider  # type: ignore[import-not-found]
            except ImportError as exc:
                raise ConfigError("Install genblaze-replicate for the configured Replicate provider.") from exc
            return ReplicateProvider(api_token=self.api_key)

        raise ConfigError(f"Unsupported Phase 0 provider: {self.provider}")

    def _from_genblaze_result(self, result: Any) -> GeneratedAsset:
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
    failure = _result_failure_message(result)
    if failure:
        raise ConfigError(f"Genblaze generation failed: {failure}")

    for asset in _iter_assets(result):
        for attr in ("bytes", "data", "content"):
            value = getattr(asset, attr, None)
            if isinstance(value, bytes):
                return value

        for attr in ("path", "local_path", "file_path"):
            value = getattr(asset, attr, None)
            if value:
                path = Path(str(value))
                if path.exists():
                    return path.read_bytes()

        url = getattr(asset, "url", None)
        if isinstance(url, str) and url.startswith(("http://", "https://")):
            return _download_url(url)

    for attr in ("bytes", "data", "content"):
        value = getattr(result, attr, None)
        if isinstance(value, bytes):
            return value

    if isinstance(result, tuple):
        for item in result:
            try:
                return _extract_bytes(item)
            except ConfigError:
                continue

    if isinstance(result, bytes):
        return result

    if isinstance(result, dict):
        for key in ("bytes", "data", "content"):
            value = result.get(key)
            if isinstance(value, bytes):
                return value

    raise ConfigError(
        "Could not extract image bytes from Genblaze result. "
        "The SDK may have returned only remote asset URLs; update the adapter to fetch or use the generated asset path."
    )


def _extract_metadata(result: Any) -> dict[str, Any]:
    run, manifest = _split_run_manifest(result)
    metadata: dict[str, Any] = {
        "result_type": type(result).__name__,
    }

    if run is not None:
        metadata["run_id"] = getattr(run, "run_id", None)
        metadata["tenant_id"] = getattr(run, "tenant_id", None)

    if manifest is not None:
        metadata["manifest_uri"] = getattr(manifest, "manifest_uri", None)
        metadata["canonical_hash"] = getattr(manifest, "canonical_hash", None)
        verify = getattr(manifest, "verify", None)
        if callable(verify):
            try:
                metadata["verified"] = bool(verify())
            except Exception:
                metadata["verified"] = None

    assets = list(_iter_assets(result))
    if assets:
        asset = assets[0]
        metadata["asset_url"] = getattr(asset, "url", None)
        metadata["asset_sha256"] = getattr(asset, "sha256", None)
        metadata["mime_type"] = getattr(asset, "mime_type", None) or "image/png"

    if isinstance(result, dict):
        metadata.update({key: value for key, value in result.items() if key not in {"bytes", "data", "content"}})
        return _drop_none(metadata)

    result_metadata = getattr(result, "metadata", None)
    if isinstance(result_metadata, dict):
        metadata.update(result_metadata)

    return _drop_none(metadata)


def _split_run_manifest(result: Any) -> tuple[Any | None, Any | None]:
    if isinstance(result, tuple) and len(result) == 2:
        return result[0], result[1]

    run = getattr(result, "run", None)
    manifest = getattr(result, "manifest", None)
    if run is not None or manifest is not None:
        return run, manifest

    return result, None


def _iter_assets(result: Any) -> list[Any]:
    run, _manifest = _split_run_manifest(result)
    steps = getattr(run, "steps", None)
    if not steps:
        return []

    assets: list[Any] = []
    for step in steps:
        step_assets = getattr(step, "assets", None) or []
        assets.extend(step_assets)
    return assets


def _drop_none(values: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in values.items() if value is not None}


def _download_url(url: str) -> bytes:
    try:
        import httpx
    except ImportError as exc:
        raise ConfigError("httpx is required to fetch remote Genblaze asset URLs.") from exc

    response = httpx.get(url, timeout=120.0)
    response.raise_for_status()
    return response.content


def _result_failure_message(result: Any) -> str | None:
    run, _manifest = _split_run_manifest(result)
    steps = getattr(run, "steps", None)
    if not steps:
        return None

    messages: list[str] = []
    for step in steps:
        error = getattr(step, "error", None) or getattr(step, "failure", None)
        status = str(getattr(step, "status", "")).lower()
        if error:
            messages.append(str(error))
        elif "fail" in status or "error" in status:
            messages.append(f"step status={status}")

    return "; ".join(messages) if messages else None
