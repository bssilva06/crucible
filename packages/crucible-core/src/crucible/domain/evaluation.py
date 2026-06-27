from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum

from pydantic import Field, model_validator

from crucible.domain.base import CrucibleModel
from crucible.domain.rubric import EvaluatorKind


class EvaluationStatus(StrEnum):
    NOT_RUN = "NOT_RUN"
    PASSED = "PASSED"
    FAILED = "FAILED"


class CriterionResult(CrucibleModel):
    criterion_id: str
    passed: bool
    score: float | None = Field(default=None, ge=0, le=1)
    hard_gate: bool
    evaluator: EvaluatorKind | str
    feedback: str | None = None
    evidence: dict[str, object] = Field(default_factory=dict)
    evaluated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class RoundVerdict(CrucibleModel):
    passed: bool
    selected_attempt_id: str | None = None
    quality_score: float = Field(ge=0, le=1)
    confidence: float = Field(ge=0, le=1)
    feedback: str
    criterion_failures: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def selected_attempt_required_when_passed(self) -> "RoundVerdict":
        if self.passed and self.selected_attempt_id is None:
            raise ValueError("selected_attempt_id is required when verdict passed is true")
        return self


def failed_hard_gates(results: list[CriterionResult]) -> list[str]:
    return [result.criterion_id for result in results if result.hard_gate and not result.passed]


def evaluation_status(results: list[CriterionResult]) -> EvaluationStatus:
    if not results:
        return EvaluationStatus.NOT_RUN
    return EvaluationStatus.FAILED if failed_hard_gates(results) else EvaluationStatus.PASSED


def aggregate_round_verdict(
    results: list[CriterionResult],
    *,
    selected_attempt_id: str | None = None,
) -> RoundVerdict:
    if not results:
        return RoundVerdict(
            passed=False,
            selected_attempt_id=None,
            quality_score=0.0,
            confidence=0.0,
            feedback="No criterion results were available.",
            criterion_failures=[],
        )

    failures = failed_hard_gates(results)
    passed = not failures
    return RoundVerdict(
        passed=passed,
        selected_attempt_id=selected_attempt_id if passed else None,
        quality_score=_quality_score(results),
        confidence=1.0,
        feedback=_feedback(failures),
        criterion_failures=failures,
    )


def to_genblaze_evaluation_result(verdict: RoundVerdict):
    try:
        from genblaze_core import EvaluationResult
    except ImportError:
        try:
            from genblaze import EvaluationResult
        except ImportError as exc:
            raise RuntimeError("Genblaze EvaluationResult is not available.") from exc

    return EvaluationResult(
        passed=verdict.passed,
        score=verdict.quality_score,
        feedback=verdict.feedback,
    )


def _quality_score(results: list[CriterionResult]) -> float:
    if not results:
        return 0.0
    total = sum(result.score if result.score is not None else 0.0 for result in results)
    return max(0.0, min(total / len(results), 1.0))


def _feedback(failures: list[str]) -> str:
    if failures:
        return f"Failed deterministic hard gates: {', '.join(failures)}."
    return "All deterministic hard gates passed."
