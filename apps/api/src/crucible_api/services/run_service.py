from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Literal
from uuid import uuid4

from pydantic import BaseModel, Field

from crucible.checks.deterministic import run_deterministic_checks
from crucible.domain.candidate import AssetRef, CandidateAttempt, CandidateStatus, select_winner
from crucible.domain.evaluation import (
    CriterionResult,
    EvaluationStatus,
    JudgeStatus,
    RoundVerdict,
    aggregate_round_verdict,
    evaluation_status,
    failed_hard_gates,
)
from crucible.domain.rubric import CriterionType, load_rubric
from crucible.judge.base import JudgeRunResult
from crucible.judge.factory import build_judge
from crucible.phase0.brief import Brief
from crucible.phase0.config import ConfigError, Phase0Settings, phase2_fanout_config, phase2_provider_configs
from crucible.phase0.generator import GeneratedAsset
from crucible.phase0.spine import (
    build_generator_for_provider,
    build_storage,
    persist_generated_candidate_asset,
    verify_manifest,
)
from crucible.phase0.storage import Storage
from crucible_api.settings import ApiSettings


RunStatus = Literal["CREATED", "GENERATING", "STORING", "VERIFYING", "COMPLETED", "FAILED"]


class RunCreateRequest(BaseModel):
    prompt: str = Field(min_length=1)
    brief_id: str | None = None
    dry_run: bool | None = None
    candidate_count: int | None = Field(default=None, ge=1, le=8)


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
    verdict: RoundVerdict | None = None
    judge_status: JudgeStatus = JudgeStatus.NOT_RUN
    judge_provider: str | None = None
    judge_model: str | None = None
    judge_error: str | None = None
    candidates: list[CandidateAttempt] = Field(default_factory=list)
    selected_attempt_id: str | None = None
    candidate_count: int = 0
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
            fanout = phase2_fanout_config(self.settings.config_root)
            requested_candidate_count = request.candidate_count or fanout["default_candidate_count"]
            provider_configs = phase2_provider_configs(self.settings.config_root, requested_candidate_count)

            self._runs[run_id] = response.model_copy(update={"status": "GENERATING"})
            brief = Brief(
                brief_id=request.brief_id or run_id,
                prompt=prompt,
            )
            rubric = load_rubric(self.settings.config_root / "rubrics" / "ecommerce-product-shot.yaml")
            candidates = _run_candidate_fanout(
                run_id=run_id,
                brief=brief,
                dry_run=dry_run,
                settings=settings,
                config_root=self.settings.config_root,
                storage=storage,
                provider_configs=provider_configs,
                rubric=rubric,
            )

            selected = select_winner(candidates)
            candidates = _mark_selection(candidates, selected.attempt_id if selected else None)
            selected = select_winner(candidates)
            response_update = {
                "status": "COMPLETED",
                "verification_status": "verified",
                "candidates": candidates,
                "candidate_count": len(candidates),
                "selected_attempt_id": selected.attempt_id if selected else None,
            }
            if selected is not None and selected.asset is not None and selected.verdict is not None:
                response_update.update(
                    {
                        "provider": selected.provider,
                        "model": selected.model,
                        "asset_uri": selected.asset.uri,
                        "manifest_uri": selected.manifest_uri,
                        "asset_sha256": selected.asset.sha256,
                        "evaluation_status": evaluation_status(selected.criterion_results),
                        "criterion_results": selected.criterion_results,
                        "failed_hard_gates": failed_hard_gates(selected.criterion_results),
                        "verdict": selected.verdict,
                        "judge_status": selected.judge_status,
                        "judge_provider": _judge_provider(selected),
                        "judge_model": _judge_model(selected),
                        "judge_error": selected.error if selected.judge_status == JudgeStatus.ERROR else None,
                    }
                )
            else:
                response_update.update(
                    {
                        "evaluation_status": EvaluationStatus.FAILED,
                        "criterion_results": [],
                        "failed_hard_gates": _bundle_failed_gates(candidates),
                        "verdict": _failed_bundle_verdict(candidates),
                        "judge_status": _bundle_judge_status(candidates),
                        "judge_provider": None,
                        "judge_model": None,
                        "judge_error": None,
                    }
                )

            completed = self._runs[run_id].model_copy(update=response_update)
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

    def get_candidate_asset(self, run_id: str, attempt_id: str) -> tuple[bytes, str]:
        record = self._runs.get(run_id)
        if record is None:
            raise KeyError(run_id)
        candidate = next((candidate for candidate in record.candidates if candidate.attempt_id == attempt_id), None)
        if candidate is None:
            raise KeyError(attempt_id)
        if candidate.asset is None:
            raise RunServiceError("Candidate has no asset")

        storage = self._storage_for_record(record)
        data = storage.get_bytes(candidate.asset.uri)
        return data, candidate.asset.mime_type or _mime_type_for_uri(candidate.asset.uri)

    def _storage_for_record(self, record: RunResponse) -> Storage:
        settings = Phase0Settings.from_env()
        candidate_asset_uris = [
            candidate.asset.uri
            for candidate in record.candidates
            if candidate.asset is not None and candidate.asset.uri
        ]
        dry_run = bool(
            (record.asset_uri and record.asset_uri.startswith("b2://local/"))
            or any(uri.startswith("b2://local/") for uri in candidate_asset_uris)
        )
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


def _run_candidate_fanout(
    *,
    run_id: str,
    brief: Brief,
    dry_run: bool,
    settings: Phase0Settings,
    config_root,
    storage: Storage,
    provider_configs: list[dict[str, object]],
    rubric,
) -> list[CandidateAttempt]:
    max_workers = min(len(provider_configs), 4)
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {
            executor.submit(
                _run_candidate_attempt,
                run_id=run_id,
                candidate_index=index,
                brief=brief,
                dry_run=dry_run,
                settings=settings,
                config_root=config_root,
                storage=storage,
                provider_config=provider_config,
                rubric=rubric,
            ): index
            for index, provider_config in enumerate(provider_configs)
        }
        candidates = [future.result() for future in as_completed(futures)]
    return sorted(candidates, key=lambda candidate: candidate.candidate_index)


def _run_candidate_attempt(
    *,
    run_id: str,
    candidate_index: int,
    brief: Brief,
    dry_run: bool,
    settings: Phase0Settings,
    config_root,
    storage: Storage,
    provider_config: dict[str, object],
    rubric,
) -> CandidateAttempt:
    provider = str(provider_config.get("provider", "unknown"))
    model = str(provider_config.get("model", "unknown"))
    attempt_id = f"attempt_{candidate_index + 1:03d}"
    try:
        generator = build_generator_for_provider(
            dry_run=dry_run,
            settings=settings,
            provider=provider,
            provider_config=provider_config,
        )
        generated = generator.generate(brief)
        persisted = persist_generated_candidate_asset(
            run_id=run_id,
            attempt_id=attempt_id,
            brief=brief,
            generated=generated,
            storage=storage,
        )
        verify_manifest(storage=storage, manifest_uri=persisted.manifest_uri)
        asset_bytes = storage.get_bytes(persisted.asset_uri)
        mime_type = _mime_type_for_uri(persisted.asset_uri)
        criterion_results = run_deterministic_checks(
            asset_bytes=asset_bytes,
            mime_type=mime_type,
            asset_uri=persisted.asset_uri,
            asset_sha256=persisted.asset_sha256,
            rubric=rubric,
        )
        judge_outcome = _judge_generated_asset(
            config_root=config_root,
            prompt=brief.prompt,
            asset_bytes=asset_bytes,
            mime_type=mime_type,
            deterministic_results=criterion_results,
            rubric=rubric,
        )
        if not failed_hard_gates(criterion_results) and judge_outcome.status in {JudgeStatus.SKIPPED, JudgeStatus.ERROR}:
            criterion_results = [
                *criterion_results,
                CriterionResult(
                    criterion_id="ai_judge_available",
                    passed=False,
                    score=0.0,
                    hard_gate=True,
                    evaluator="system",
                    feedback=judge_outcome.error or "AI judge did not return results.",
                    evidence={"judge_status": judge_outcome.status},
                ),
            ]
        criterion_results = [*criterion_results, *judge_outcome.results]
        failures = failed_hard_gates(criterion_results)
        status = CandidateStatus.REJECTED if failures else CandidateStatus.ELIGIBLE
        verdict = aggregate_round_verdict(criterion_results, selected_attempt_id=attempt_id)
        return CandidateAttempt(
            attempt_id=attempt_id,
            candidate_index=candidate_index,
            provider=generated.provider,
            model=generated.model,
            status=status,
            asset=AssetRef(
                uri=persisted.asset_uri,
                sha256=persisted.asset_sha256,
                mime_type=mime_type,
                bytes_size=len(asset_bytes),
            ),
            manifest_uri=persisted.manifest_uri,
            criterion_results=criterion_results,
            failed_hard_gates=failures,
            judge_status=judge_outcome.status,
            verdict=verdict,
            error=judge_outcome.error if judge_outcome.status == JudgeStatus.ERROR else None,
        )
    except Exception as exc:
        return CandidateAttempt(
            attempt_id=attempt_id,
            candidate_index=candidate_index,
            provider=provider,
            model=model,
            status=CandidateStatus.FAILED,
            error=_sanitize_error(exc),
        )


def _mark_selection(candidates: list[CandidateAttempt], selected_attempt_id: str | None) -> list[CandidateAttempt]:
    marked: list[CandidateAttempt] = []
    for candidate in candidates:
        if selected_attempt_id and candidate.attempt_id == selected_attempt_id:
            marked.append(candidate.model_copy(update={"selection_reason": "Selected highest-scoring eligible candidate."}))
        elif candidate.status == CandidateStatus.ELIGIBLE:
            marked.append(candidate.model_copy(update={"selection_reason": "Eligible but not selected."}))
        elif candidate.status == CandidateStatus.REJECTED:
            marked.append(candidate.model_copy(update={"selection_reason": "Rejected by failed hard gates."}))
        elif candidate.status == CandidateStatus.FAILED:
            marked.append(candidate.model_copy(update={"selection_reason": "Candidate failed before evaluation completed."}))
        else:
            marked.append(candidate)
    return marked


def _bundle_failed_gates(candidates: list[CandidateAttempt]) -> list[str]:
    failures: list[str] = []
    for candidate in candidates:
        for gate in candidate.failed_hard_gates:
            if gate not in failures:
                failures.append(gate)
    return failures


def _failed_bundle_verdict(candidates: list[CandidateAttempt]) -> RoundVerdict:
    failures = _bundle_failed_gates(candidates)
    return RoundVerdict(
        passed=False,
        selected_attempt_id=None,
        quality_score=0.0,
        confidence=0.0,
        feedback="No eligible candidate passed all hard gates.",
        criterion_failures=failures,
    )


def _bundle_judge_status(candidates: list[CandidateAttempt]) -> JudgeStatus:
    statuses = [candidate.judge_status for candidate in candidates]
    if any(status == JudgeStatus.ERROR for status in statuses):
        return JudgeStatus.ERROR
    if any(status == JudgeStatus.FAILED for status in statuses):
        return JudgeStatus.FAILED
    if any(status == JudgeStatus.PASSED for status in statuses):
        return JudgeStatus.PASSED
    if any(status == JudgeStatus.SKIPPED for status in statuses):
        return JudgeStatus.SKIPPED
    return JudgeStatus.NOT_RUN


def _judge_provider(candidate: CandidateAttempt) -> str | None:
    judge_results = [result for result in candidate.criterion_results if result.evaluator != "deterministic"]
    if judge_results:
        evaluator = str(judge_results[0].evaluator)
        if evaluator.startswith("gemini"):
            return "gemini"
        if evaluator.startswith("fake"):
            return "fake"
        return evaluator
    return None


def _judge_model(candidate: CandidateAttempt) -> str | None:
    judge_results = [result for result in candidate.criterion_results if result.evaluator != "deterministic"]
    return str(judge_results[0].evaluator) if judge_results else None


def _judge_generated_asset(
    *,
    config_root,
    prompt: str,
    asset_bytes: bytes,
    mime_type: str,
    deterministic_results: list[CriterionResult],
    rubric,
) -> JudgeRunResult:
    if failed_hard_gates(deterministic_results):
        return JudgeRunResult(
            status=JudgeStatus.SKIPPED,
            error="Skipped because deterministic hard gates failed.",
        )

    criteria = [criterion for criterion in rubric.criteria if criterion.type == CriterionType.VLM_BOOLEAN]
    judge = build_judge(config_root)
    return judge.evaluate(
        prompt=prompt,
        asset_bytes=asset_bytes,
        mime_type=mime_type,
        criteria=criteria,
    )


def _sanitize_error(exc: Exception) -> str:
    text = str(exc)
    forbidden = [
        "GMI_API_KEY",
        "GMICLOUD_API_KEY",
        "B2_APPLICATION_KEY",
        "B2_APP_KEY",
        "REPLICATE_API_TOKEN",
        "GEMINI_API_KEY",
        "GOOGLE_API_KEY",
    ]
    for token in forbidden:
        text = text.replace(token, "<redacted-env>")
    return text
