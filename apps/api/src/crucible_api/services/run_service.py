from __future__ import annotations

from typing import Literal
from uuid import uuid4

from pydantic import BaseModel, Field

from crucible.checks.deterministic import run_deterministic_checks
from crucible.domain.evaluation import CriterionResult, EvaluationStatus, evaluation_status, failed_hard_gates
from crucible.domain.rubric import load_rubric
from crucible.phase0.brief import Brief
from crucible.phase0.config import ConfigError, Phase0Settings
from crucible.phase0.generator import GeneratedAsset
from crucible.phase0.spine import build_generator, build_storage, persist_generated_asset, verify_manifest
from crucible.phase0.storage import Storage
from crucible_api.settings import ApiSettings


RunStatus = Literal["CREATED", "GENERATING", "STORING", "VERIFYING", "COMPLETED", "FAILED"]


class RunCreateRequest(BaseModel):
    prompt: str = Field(min_length=1)
    brief_id: str | None = None
    dry_run: bool | None = None


class RunResponse(BaseModel):
    run_id: str
    status: RunStatus
    prompt: str
    provider: str | None = None
    model: str | None = None
    asset_uri: str | None = None
    manifest_uri: str | None = None
    asset_sha256: str | None = None
    verification_status: Literal["pending", "verified", "failed"] = "pending"
    evaluation_status: EvaluationStatus = EvaluationStatus.NOT_RUN
    criterion_results: list[CriterionResult] = Field(default_factory=list)
    failed_hard_gates: list[str] = Field(default_factory=list)
    error: str | None = None


class RunServiceError(RuntimeError):
    pass


class RunService:
    def __init__(self, settings: ApiSettings) -> None:
        self.settings = settings
        self._runs: dict[str, RunResponse] = {}

    def create_run(self, request: RunCreateRequest) -> RunResponse:
        prompt = request.prompt.strip()
        if not prompt:
            raise RunServiceError("Prompt is required")
        if len(prompt) > self.settings.max_prompt_chars:
            raise RunServiceError(f"Prompt must be {self.settings.max_prompt_chars} characters or fewer")

        dry_run = self.settings.dry_run_default if request.dry_run is None else request.dry_run
        if dry_run and not self.settings.allow_dry_run:
            raise RunServiceError("Dry run is disabled for this environment")

        run_id = f"run_{uuid4().hex}"
        response = RunResponse(
            run_id=run_id,
            status="CREATED",
            prompt=prompt,
        )
        self._runs[run_id] = response

        try:
            settings = Phase0Settings.from_env()
            storage = build_storage(
                dry_run=dry_run,
                settings=settings,
                local_root=self.settings.local_storage_root,
            )
            generator = build_generator(
                dry_run=dry_run,
                settings=settings,
                config_root=self.settings.config_root,
            )

            self._runs[run_id] = response.model_copy(update={"status": "GENERATING"})
            brief = Brief(
                brief_id=request.brief_id or run_id,
                prompt=prompt,
            )
            generated = generator.generate(brief)

            self._runs[run_id] = self._runs[run_id].model_copy(
                update={
                    "status": "STORING",
                    "provider": generated.provider,
                    "model": generated.model,
                }
            )
            result = persist_generated_asset(
                run_id=run_id,
                brief=brief,
                generated=generated,
                storage=storage,
            )

            self._runs[run_id] = self._runs[run_id].model_copy(
                update={
                    "status": "VERIFYING",
                    "asset_uri": result.asset_uri,
                    "manifest_uri": result.manifest_uri,
                    "asset_sha256": result.asset_sha256,
                    "verification_status": "pending",
                }
            )
            verify_manifest(storage=storage, run_id=run_id)
            asset_bytes = storage.get_bytes(result.asset_uri)
            rubric = load_rubric(self.settings.config_root / "rubrics" / "ecommerce-product-shot.yaml")
            criterion_results = run_deterministic_checks(
                asset_bytes=asset_bytes,
                mime_type=_mime_type_for_uri(result.asset_uri),
                asset_uri=result.asset_uri,
                asset_sha256=result.asset_sha256,
                rubric=rubric,
            )
            completed = self._runs[run_id].model_copy(
                update={
                    "status": "COMPLETED",
                    "verification_status": "verified",
                    "evaluation_status": evaluation_status(criterion_results),
                    "criterion_results": criterion_results,
                    "failed_hard_gates": failed_hard_gates(criterion_results),
                }
            )
            self._runs[run_id] = completed
            return completed
        except (ConfigError, ValueError, FileNotFoundError, OSError) as exc:
            failed = self._runs[run_id].model_copy(
                update={
                    "status": "FAILED",
                    "verification_status": "failed",
                    "error": _sanitize_error(exc),
                }
            )
            self._runs[run_id] = failed
            return failed

    def get_run(self, run_id: str) -> RunResponse | None:
        return self._runs.get(run_id)

    def get_asset(self, run_id: str) -> tuple[bytes, str]:
        record = self._runs.get(run_id)
        if record is None:
            raise KeyError(run_id)
        if record.status != "COMPLETED" or not record.asset_uri:
            raise RunServiceError("Run has no completed asset")

        storage = self._storage_for_record(record)
        data = storage.get_bytes(record.asset_uri)
        return data, _mime_type_for_uri(record.asset_uri)

    def _storage_for_record(self, record: RunResponse) -> Storage:
        settings = Phase0Settings.from_env()
        dry_run = bool(record.asset_uri and record.asset_uri.startswith("b2://local/"))
        return build_storage(
            dry_run=dry_run,
            settings=settings,
            local_root=self.settings.local_storage_root,
        )


_service: RunService | None = None


def get_run_service() -> RunService:
    global _service
    if _service is None:
        _service = RunService(ApiSettings.load())
    return _service


def reset_run_service_for_tests(settings: ApiSettings | None = None) -> RunService:
    global _service
    _service = RunService(settings or ApiSettings.load())
    return _service


def _mime_type_for_uri(uri: str) -> str:
    if uri.lower().endswith(".png"):
        return "image/png"
    if uri.lower().endswith((".jpg", ".jpeg")):
        return "image/jpeg"
    return "application/octet-stream"


def _sanitize_error(exc: Exception) -> str:
    text = str(exc)
    forbidden = ["GMI_API_KEY", "GMICLOUD_API_KEY", "B2_APPLICATION_KEY", "B2_APP_KEY", "REPLICATE_API_TOKEN"]
    for token in forbidden:
        text = text.replace(token, "<redacted-env>")
    return text
