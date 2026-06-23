from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4

from crucible.phase0.brief import Brief
from crucible.phase0.config import Phase0Settings, phase0_provider_config
from crucible.phase0.crypto import sha256_bytes
from crucible.phase0.generator import DryRunGenerator, GeneratedAsset, Generator, GenblazeGenerator
from crucible.phase0.manifest import Phase0Manifest
from crucible.phase0.storage import B2Storage, LocalStorage, Storage, object_key


@dataclass(frozen=True)
class Phase0RunResult:
    run_id: str
    asset_uri: str
    manifest_uri: str
    asset_sha256: str


def build_generator(*, dry_run: bool, settings: Phase0Settings, config_root: Path) -> Generator:
    if dry_run:
        return DryRunGenerator()
    provider_config = phase0_provider_config(config_root, settings.provider)
    return GenblazeGenerator(settings=settings, provider_config=provider_config)


def build_storage(*, dry_run: bool, settings: Phase0Settings, local_root: Path) -> Storage:
    if dry_run:
        return LocalStorage(local_root)
    return B2Storage(settings)


def run_phase0(
    *,
    brief_path: Path,
    config_root: Path,
    storage: Storage,
    generator: Generator,
    run_id: str | None = None,
) -> Phase0RunResult:
    run_id = run_id or f"run_{uuid4().hex}"
    brief = Brief.from_file(brief_path)
    generated = generator.generate(brief)
    return persist_generated_asset(run_id=run_id, brief=brief, generated=generated, storage=storage)


def persist_generated_asset(
    *,
    run_id: str,
    brief: Brief,
    generated: GeneratedAsset,
    storage: Storage,
) -> Phase0RunResult:
    asset_sha256 = sha256_bytes(generated.data)
    extension = _extension_for_mime_type(generated.mime_type)
    asset_key = object_key(run_id, f"asset.{extension}")
    asset = storage.put_bytes(asset_key, generated.data, generated.mime_type)

    manifest = Phase0Manifest.create(
        run_id=run_id,
        brief_id=brief.brief_id,
        provider=generated.provider,
        model=generated.model,
        asset_uri=asset.uri,
        asset_sha256=asset_sha256,
        genblaze=generated.genblaze_metadata,
    )
    manifest_key = object_key(run_id, "manifest.json")
    manifest_object = storage.put_bytes(manifest_key, manifest.to_json_bytes(), "application/json")

    return Phase0RunResult(
        run_id=run_id,
        asset_uri=asset.uri,
        manifest_uri=manifest_object.uri,
        asset_sha256=asset_sha256,
    )


def verify_manifest(*, storage: Storage, run_id: str | None = None, manifest_uri: str | None = None) -> Phase0Manifest:
    if not run_id and not manifest_uri:
        raise ValueError("Either run_id or manifest_uri is required")

    uri_or_key = manifest_uri or object_key(run_id or "", "manifest.json")
    manifest = Phase0Manifest.from_json_bytes(storage.get_bytes(uri_or_key))
    asset_bytes = storage.get_bytes(manifest.asset_uri)
    actual_sha256 = sha256_bytes(asset_bytes)
    if actual_sha256 != manifest.asset_sha256:
        raise ValueError(
            f"Manifest hash mismatch for {manifest.asset_uri}: expected {manifest.asset_sha256}, got {actual_sha256}"
        )
    return manifest


def _extension_for_mime_type(mime_type: str) -> str:
    if mime_type == "image/png":
        return "png"
    if mime_type in {"image/jpeg", "image/jpg"}:
        return "jpg"
    return "bin"
