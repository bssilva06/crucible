from __future__ import annotations

from enum import StrEnum

from pydantic import Field

from crucible.domain.evaluation import CriterionResult, JudgeStatus, RoundVerdict, failed_hard_gates
from crucible.domain.base import CrucibleModel


class CandidateStatus(StrEnum):
    GENERATING = "GENERATING"
    STORING = "STORING"
    VERIFYING = "VERIFYING"
    EVALUATING = "EVALUATING"
    ELIGIBLE = "ELIGIBLE"
    REJECTED = "REJECTED"
    FAILED = "FAILED"


class AssetRef(CrucibleModel):
    uri: str
    sha256: str | None = Field(default=None, min_length=64, max_length=64)
    mime_type: str | None = None
    width: int | None = Field(default=None, ge=1)
    height: int | None = Field(default=None, ge=1)
    bytes_size: int | None = Field(default=None, ge=0)


class CandidateAttempt(CrucibleModel):
    attempt_id: str
    candidate_index: int = Field(ge=0)
    provider: str | None = None
    model: str | None = None
    status: CandidateStatus
    asset: AssetRef | None = None
    manifest_uri: str | None = None
    criterion_results: list[CriterionResult] = Field(default_factory=list)
    failed_hard_gates: list[str] = Field(default_factory=list)
    judge_status: JudgeStatus = JudgeStatus.NOT_RUN
    verdict: RoundVerdict | None = None
    error: str | None = None
    selection_reason: str | None = None

    @property
    def is_eligible(self) -> bool:
        return self.status == CandidateStatus.ELIGIBLE and bool(self.verdict and self.verdict.passed)


class CandidateBundle(CrucibleModel):
    run_id: str
    prompt: str
    candidates: list[CandidateAttempt] = Field(default_factory=list)
    selected_attempt_id: str | None = None
    candidate_count: int = Field(ge=0)
    verdict: RoundVerdict | None = None


def candidate_failed_hard_gates(results: list[CriterionResult]) -> list[str]:
    return failed_hard_gates(results)


def select_winner(candidates: list[CandidateAttempt]) -> CandidateAttempt | None:
    eligible = [candidate for candidate in candidates if candidate.is_eligible and candidate.verdict is not None]
    if not eligible:
        return None
    return max(
        eligible,
        key=lambda candidate: (
            candidate.verdict.quality_score if candidate.verdict else 0.0,
            candidate.verdict.confidence if candidate.verdict else 0.0,
            -candidate.candidate_index,
        ),
    )
