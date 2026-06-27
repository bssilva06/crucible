from __future__ import annotations

from crucible.domain.evaluation import CriterionResult, JudgeStatus
from crucible.domain.rubric import Criterion
from crucible.judge.base import JudgeRunResult


class FakeJudge:
    provider = "fake"
    model = "fake-vlm"

    def __init__(self, *, passed: bool = True, failing_ids: set[str] | None = None) -> None:
        self.passed = passed
        self.failing_ids = failing_ids or set()

    def evaluate(
        self,
        *,
        prompt: str,
        asset_bytes: bytes,
        mime_type: str,
        criteria: list[Criterion],
    ) -> JudgeRunResult:
        results: list[CriterionResult] = []
        for criterion in criteria:
            passed = self.passed and criterion.id not in self.failing_ids
            results.append(
                CriterionResult(
                    criterion_id=criterion.id,
                    passed=passed,
                    score=1.0 if passed else 0.0,
                    hard_gate=criterion.hard_gate,
                    evaluator=self.model,
                    feedback="Fake judge passed this criterion." if passed else "Fake judge failed this criterion.",
                    evidence={
                        "provider": self.provider,
                        "model": self.model,
                        "prompt_chars": len(prompt),
                        "asset_bytes": len(asset_bytes),
                        "mime_type": mime_type,
                    },
                )
            )
        return JudgeRunResult(
            status=JudgeStatus.PASSED if all(result.passed for result in results) else JudgeStatus.FAILED,
            results=results,
            provider=self.provider,
            model=self.model,
        )
