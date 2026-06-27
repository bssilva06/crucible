from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from crucible.domain.evaluation import CriterionResult, JudgeStatus, aggregate_round_verdict
from crucible.domain.rubric import CriterionType, EvaluatorKind, load_rubric
from crucible.judge.config import load_judge_config
from crucible.judge.fake import FakeJudge
from crucible.judge.gemini import parse_gemini_results


RUBRIC_PATH = Path("configs/rubrics/ecommerce-product-shot.yaml")


def test_judge_config_loads_defaults_and_masks_secret(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GOOGLE_API_KEY", "secret-value")

    config = load_judge_config(tmp_path / "missing.yaml")

    assert config.enabled is True
    assert config.provider == "gemini"
    assert config.api_key is not None
    assert config.api_key.get_secret_value() == "secret-value"
    assert "secret-value" not in str(config)


def test_fake_judge_returns_valid_criterion_results() -> None:
    criteria = _vlm_criteria()

    outcome = FakeJudge().evaluate(
        prompt="Centered bottle on white",
        asset_bytes=b"png-bytes",
        mime_type="image/png",
        criteria=criteria,
    )

    assert outcome.status == JudgeStatus.PASSED
    assert [result.criterion_id for result in outcome.results] == [criterion.id for criterion in criteria]
    assert all(result.evaluator == "fake-vlm" for result in outcome.results)


def test_parse_gemini_results_accepts_valid_structured_json() -> None:
    criteria = _vlm_criteria()
    payload = {
        "results": [
            {
                "criterion_id": criterion.id,
                "passed": True,
                "score": 1.0,
                "feedback": "Looks correct.",
                "evidence": {"criterion": criterion.id},
            }
            for criterion in criteria
        ]
    }

    results = parse_gemini_results(text=json.dumps(payload), criteria=criteria, evaluator="gemini-2.5-flash")

    assert len(results) == len(criteria)
    assert all(isinstance(result, CriterionResult) for result in results)
    assert all(result.passed for result in results)


@pytest.mark.parametrize(
    "payload",
    [
        {"results": []},
        {
            "results": [
                {
                    "criterion_id": "product_centered",
                    "passed": True,
                    "score": 2.0,
                    "feedback": "Bad score.",
                }
            ]
        },
        {
            "results": [
                {
                    "criterion_id": "product_centered",
                    "passed": True,
                    "score": 1.0,
                    "feedback": "Duplicate.",
                },
                {
                    "criterion_id": "product_centered",
                    "passed": True,
                    "score": 1.0,
                    "feedback": "Duplicate.",
                },
            ]
        },
    ],
)
def test_parse_gemini_results_rejects_invalid_payloads(payload: dict[str, object]) -> None:
    with pytest.raises((ValidationError, ValueError)):
        parse_gemini_results(text=json.dumps(payload), criteria=_vlm_criteria(), evaluator="gemini-2.5-flash")


def test_parse_gemini_results_rejects_mismatched_criteria() -> None:
    payload = {
        "results": [
            {
                "criterion_id": "unknown",
                "passed": True,
                "score": 1.0,
                "feedback": "Unexpected criterion.",
            }
        ]
    }

    with pytest.raises(ValueError):
        parse_gemini_results(text=json.dumps(payload), criteria=_vlm_criteria(), evaluator="gemini-2.5-flash")


def test_parse_gemini_results_rejects_malformed_json() -> None:
    with pytest.raises(ValueError):
        parse_gemini_results(text="not json", criteria=_vlm_criteria(), evaluator="gemini-2.5-flash")


def test_verdict_fails_when_vlm_hard_gate_fails() -> None:
    results = [
        CriterionResult(
            criterion_id="file_integrity",
            passed=True,
            score=1.0,
            hard_gate=True,
            evaluator=EvaluatorKind.DETERMINISTIC,
        ),
        CriterionResult(
            criterion_id="product_centered",
            passed=False,
            score=0.0,
            hard_gate=True,
            evaluator="gemini-2.5-flash",
        ),
    ]

    verdict = aggregate_round_verdict(results, selected_attempt_id="run_1")

    assert verdict.passed is False
    assert verdict.confidence == 0.8
    assert verdict.criterion_failures == ["product_centered"]
    assert "Failed judge hard gates: product_centered" in verdict.feedback


def _vlm_criteria():
    rubric = load_rubric(RUBRIC_PATH)
    return [criterion for criterion in rubric.criteria if criterion.type == CriterionType.VLM_BOOLEAN]
