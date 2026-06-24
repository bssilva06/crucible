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
