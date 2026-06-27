from __future__ import annotations

from typing import Protocol

from pydantic import Field

from crucible.domain.base import CrucibleModel
from crucible.domain.evaluation import CriterionResult, JudgeStatus
from crucible.domain.rubric import Criterion


class JudgeRunResult(CrucibleModel):
    status: JudgeStatus
    results: list[CriterionResult] = Field(default_factory=list)
    provider: str | None = None
    model: str | None = None
    error: str | None = None


class BriefJudge(Protocol):
    provider: str
    model: str

    def evaluate(
        self,
        *,
        prompt: str,
        asset_bytes: bytes,
        mime_type: str,
        criteria: list[Criterion],
    ) -> JudgeRunResult:
        ...
