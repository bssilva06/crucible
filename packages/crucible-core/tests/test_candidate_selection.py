from __future__ import annotations

from crucible.domain.candidate import CandidateAttempt, CandidateStatus, select_winner
from crucible.domain.evaluation import CriterionResult, RoundVerdict
from crucible.domain.rubric import EvaluatorKind


def test_candidate_with_failed_hard_gate_is_not_eligible() -> None:
    candidate = CandidateAttempt(
        attempt_id="attempt_001",
        candidate_index=0,
        status=CandidateStatus.REJECTED,
        criterion_results=[_criterion("minimum_resolution", passed=False)],
        failed_hard_gates=["minimum_resolution"],
        verdict=_verdict(passed=False, score=0.0, confidence=1.0),
    )

    assert candidate.is_eligible is False
    assert select_winner([candidate]) is None


def test_select_winner_chooses_highest_eligible_score() -> None:
    winner = select_winner(
        [
            _candidate("attempt_001", 0, score=0.7, confidence=0.8),
            _candidate("attempt_002", 1, score=0.9, confidence=0.8),
        ]
    )

    assert winner is not None
    assert winner.attempt_id == "attempt_002"


def test_select_winner_tiebreaks_by_confidence_then_index() -> None:
    confidence_winner = select_winner(
        [
            _candidate("attempt_001", 0, score=0.9, confidence=0.7),
            _candidate("attempt_002", 1, score=0.9, confidence=0.8),
        ]
    )
    index_winner = select_winner(
        [
            _candidate("attempt_001", 0, score=0.9, confidence=0.8),
            _candidate("attempt_002", 1, score=0.9, confidence=0.8),
        ]
    )

    assert confidence_winner is not None
    assert confidence_winner.attempt_id == "attempt_002"
    assert index_winner is not None
    assert index_winner.attempt_id == "attempt_001"


def test_failed_candidate_does_not_block_successful_candidate() -> None:
    winner = select_winner(
        [
            CandidateAttempt(
                attempt_id="attempt_001",
                candidate_index=0,
                status=CandidateStatus.FAILED,
                error="Provider failed.",
            ),
            _candidate("attempt_002", 1, score=0.8, confidence=0.8),
        ]
    )

    assert winner is not None
    assert winner.attempt_id == "attempt_002"


def _candidate(attempt_id: str, index: int, *, score: float, confidence: float) -> CandidateAttempt:
    return CandidateAttempt(
        attempt_id=attempt_id,
        candidate_index=index,
        status=CandidateStatus.ELIGIBLE,
        criterion_results=[_criterion("file_integrity", passed=True)],
        failed_hard_gates=[],
        verdict=_verdict(passed=True, score=score, confidence=confidence, selected_attempt_id=attempt_id),
    )


def _criterion(criterion_id: str, *, passed: bool) -> CriterionResult:
    return CriterionResult(
        criterion_id=criterion_id,
        passed=passed,
        score=1.0 if passed else 0.0,
        hard_gate=True,
        evaluator=EvaluatorKind.DETERMINISTIC,
    )


def _verdict(
    *,
    passed: bool,
    score: float,
    confidence: float,
    selected_attempt_id: str | None = None,
) -> RoundVerdict:
    return RoundVerdict(
        passed=passed,
        selected_attempt_id=selected_attempt_id if passed else None,
        quality_score=score,
        confidence=confidence,
        feedback="test verdict",
        criterion_failures=[] if passed else ["minimum_resolution"],
    )
