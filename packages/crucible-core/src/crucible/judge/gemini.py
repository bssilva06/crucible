from __future__ import annotations

import base64
import json

from pydantic import BaseModel, Field, ValidationError, field_validator

from crucible.domain.evaluation import CriterionResult, JudgeStatus
from crucible.domain.rubric import Criterion
from crucible.judge.base import JudgeRunResult
from crucible.judge.config import JudgeConfig


class GeminiCriterionResult(BaseModel):
    criterion_id: str
    passed: bool
    score: float = Field(ge=0, le=1)
    feedback: str
    evidence: dict[str, object] = Field(default_factory=dict)


class GeminiJudgeResponse(BaseModel):
    results: list[GeminiCriterionResult] = Field(min_length=1)

    @field_validator("results")
    @classmethod
    def result_ids_are_unique(cls, results: list[GeminiCriterionResult]) -> list[GeminiCriterionResult]:
        ids = [result.criterion_id for result in results]
        if len(ids) != len(set(ids)):
            raise ValueError("Gemini response criterion ids must be unique")
        return results


class GeminiJudge:
    provider = "gemini"

    def __init__(self, *, config: JudgeConfig) -> None:
        self.config = config
        self.model = config.model

    def evaluate(
        self,
        *,
        prompt: str,
        asset_bytes: bytes,
        mime_type: str,
        criteria: list[Criterion],
    ) -> JudgeRunResult:
        if not criteria:
            return JudgeRunResult(status=JudgeStatus.SKIPPED, provider=self.provider, model=self.model, error="No VLM criteria.")

        try:
            from google import genai  # type: ignore[import-not-found]
        except ImportError:
            return JudgeRunResult(
                status=JudgeStatus.ERROR,
                provider=self.provider,
                model=self.model,
                error="google-genai is not installed.",
            )

        api_key = self.config.api_key.get_secret_value() if self.config.api_key else None
        try:
            client = genai.Client(api_key=api_key)
            interaction = client.interactions.create(
                model=self.model,
                input=[
                    {"type": "text", "text": _prompt(prompt=prompt, criteria=criteria)},
                    {
                        "type": "image",
                        "data": base64.b64encode(asset_bytes).decode("ascii"),
                        "mime_type": mime_type,
                    },
                ],
                response_format={
                    "type": "text",
                    "mime_type": "application/json",
                    "schema": GeminiJudgeResponse.model_json_schema(),
                },
            )
            results = parse_gemini_results(
                text=interaction.output_text,
                criteria=criteria,
                evaluator=self.model,
            )
            return JudgeRunResult(
                status=JudgeStatus.PASSED if all(result.passed for result in results) else JudgeStatus.FAILED,
                results=results,
                provider=self.provider,
                model=self.model,
            )
        except (AttributeError, TypeError, ValueError, ValidationError, OSError) as exc:
            return JudgeRunResult(
                status=JudgeStatus.ERROR,
                provider=self.provider,
                model=self.model,
                error=_sanitize_error(str(exc)),
            )


def parse_gemini_results(*, text: str, criteria: list[Criterion], evaluator: str) -> list[CriterionResult]:
    payload = json.loads(text)
    response = GeminiJudgeResponse.model_validate(payload)
    criteria_by_id = {criterion.id: criterion for criterion in criteria}
    response_ids = {result.criterion_id for result in response.results}
    expected_ids = set(criteria_by_id)
    if response_ids != expected_ids:
        missing = sorted(expected_ids - response_ids)
        extra = sorted(response_ids - expected_ids)
        raise ValueError(f"Gemini response criteria mismatch; missing={missing}; extra={extra}")

    results: list[CriterionResult] = []
    for result in response.results:
        criterion = criteria_by_id[result.criterion_id]
        results.append(
            CriterionResult(
                criterion_id=result.criterion_id,
                passed=result.passed,
                score=result.score,
                hard_gate=criterion.hard_gate,
                evaluator=evaluator,
                feedback=result.feedback,
                evidence=result.evidence,
            )
        )
    return results


def _prompt(*, prompt: str, criteria: list[Criterion]) -> str:
    criteria_text = "\n".join(f"- {criterion.id}: {criterion.description}" for criterion in criteria)
    return (
        "You are Crucible's brief-aware e-commerce product image judge.\n"
        "Judge the image against the user brief and each criterion. "
        "Return only JSON matching the provided schema.\n\n"
        f"User brief:\n{prompt}\n\n"
        f"Criteria:\n{criteria_text}\n\n"
        "For each criterion, set passed to true only when the image clearly satisfies it. "
        "Use score 1.0 for clear pass, 0.0 for clear fail, or an intermediate value for uncertainty. "
        "Keep feedback short and specific."
    )


def _sanitize_error(text: str) -> str:
    for token in ("GEMINI_API_KEY", "GOOGLE_API_KEY"):
        text = text.replace(token, "<redacted-env>")
    return text
