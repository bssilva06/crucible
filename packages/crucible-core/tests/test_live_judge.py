from __future__ import annotations

import os
from io import BytesIO
from pathlib import Path

import pytest
from PIL import Image

from crucible.domain.evaluation import JudgeStatus
from crucible.domain.rubric import CriterionType, load_rubric
from crucible.judge.config import JudgeConfig
from crucible.judge.gemini import GeminiJudge


@pytest.mark.skipif(
    os.getenv("CRUCIBLE_RUN_LIVE_JUDGE_TESTS", "").lower() not in {"1", "true", "yes", "on"},
    reason="live Gemini judge tests are opt-in",
)
def test_live_gemini_judge_returns_structured_results() -> None:
    api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    if not api_key:
        pytest.skip("GEMINI_API_KEY or GOOGLE_API_KEY is required for live judge tests")

    rubric = load_rubric(Path("configs/rubrics/ecommerce-product-shot.yaml"))
    criteria = [criterion for criterion in rubric.criteria if criterion.type == CriterionType.VLM_BOOLEAN]
    judge = GeminiJudge(config=JudgeConfig(api_key=api_key))

    outcome = judge.evaluate(
        prompt="A centered product on a plain white background with no text, people, props, or logos.",
        asset_bytes=_white_png(),
        mime_type="image/png",
        criteria=criteria,
    )

    assert outcome.status in {JudgeStatus.PASSED, JudgeStatus.FAILED}
    assert [result.criterion_id for result in outcome.results] == [criterion.id for criterion in criteria]


def _white_png() -> bytes:
    image = Image.new("RGB", (512, 512), (255, 255, 255))
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()
