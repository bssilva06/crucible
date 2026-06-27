from __future__ import annotations

from crucible.domain.evaluation import CriterionResult, aggregate_round_verdict
from crucible.domain.rubric import EvaluatorKind


def test_all_hard_gates_pass_yields_passing_verdict() -> None:
    verdict = aggregate_round_verdict(
        [
            _result("file_integrity", passed=True, score=1.0),
            _result("minimum_resolution", passed=True, score=0.8),
        ],
        selected_attempt_id="attempt_1",
    )

    assert verdict.passed is True
    assert verdict.selected_attempt_id == "attempt_1"
    assert verdict.quality_score == 0.9
    assert verdict.confidence == 1.0
    assert verdict.feedback == "All deterministic hard gates passed."
    assert verdict.criterion_failures == []


def test_failed_hard_gate_yields_failing_verdict() -> None:
    verdict = aggregate_round_verdict(
        [
            _result("file_integrity", passed=True, score=1.0),
            _result("minimum_resolution", passed=False, score=0.0),
        ],
        selected_attempt_id="attempt_1",
    )

    assert verdict.passed is False
    assert verdict.selected_attempt_id is None
    assert verdict.quality_score == 0.5
    assert verdict.confidence == 1.0
    assert verdict.feedback == "Failed deterministic hard gates: minimum_resolution."
    assert verdict.criterion_failures == ["minimum_resolution"]


def test_no_results_yields_not_passed_zero_confidence_verdict() -> None:
    verdict = aggregate_round_verdict([])

    assert verdict.passed is False
    assert verdict.quality_score == 0.0
    assert verdict.confidence == 0.0
    assert verdict.feedback == "No criterion results were available."


def test_null_scores_count_as_zero() -> None:
    verdict = aggregate_round_verdict(
        [
            _result("file_integrity", passed=True, score=1.0),
            _result("minimum_resolution", passed=True, score=None),
        ],
        selected_attempt_id="attempt_1",
    )

    assert verdict.passed is True
    assert verdict.quality_score == 0.5


def _result(criterion_id: str, *, passed: bool, score: float | None) -> CriterionResult:
    return CriterionResult(
        criterion_id=criterion_id,
        passed=passed,
        score=score,
        hard_gate=True,
        evaluator=EvaluatorKind.DETERMINISTIC,
        feedback=None,
        evidence={},
    )
