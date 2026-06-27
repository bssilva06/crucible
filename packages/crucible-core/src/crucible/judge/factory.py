from __future__ import annotations

from pathlib import Path

from crucible.domain.evaluation import JudgeStatus
from crucible.judge.base import JudgeRunResult
from crucible.judge.config import load_judge_config
from crucible.judge.fake import FakeJudge
from crucible.judge.gemini import GeminiJudge


class SkippedJudge:
    provider = "none"
    model = "none"

    def __init__(self, reason: str) -> None:
        self.reason = reason

    def evaluate(self, **_: object) -> JudgeRunResult:
        return JudgeRunResult(status=JudgeStatus.SKIPPED, provider=self.provider, model=self.model, error=self.reason)


def build_judge(config_root: Path):
    config = load_judge_config(config_root / "judge.yaml")
    provider = config.provider.strip().lower()
    if not config.enabled:
        return SkippedJudge("Judge is disabled.")
    if provider == "fake":
        return FakeJudge()
    if provider != "gemini":
        return SkippedJudge(f"Judge provider '{config.provider}' is not supported.")
    if config.api_key is None:
        return SkippedJudge("Gemini judge credentials are not configured.")
    return GeminiJudge(config=config)
