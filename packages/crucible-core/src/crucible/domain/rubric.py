from __future__ import annotations

from enum import StrEnum
from pathlib import Path
from typing import Any

from pydantic import Field, field_validator

from crucible.domain.base import CrucibleModel


class CriterionType(StrEnum):
    ASPECT_RATIO = "aspect_ratio"
    RESOLUTION = "resolution"
    FILE_INTEGRITY = "file_integrity"
    PIXEL_BACKGROUND_CHECK = "pixel_background_check"
    OCR_EXACT_MATCH = "ocr_exact_match"
    OCR_SIMILARITY = "ocr_similarity"
    VLM_BOOLEAN = "vlm_boolean"
    VLM_RANKING = "vlm_ranking"
    SAFETY = "safety"
    BRAND = "brand"
    IP_RISK = "ip_risk"


class EvaluatorKind(StrEnum):
    DETERMINISTIC = "deterministic"
    PADDLE_OCR = "paddleocr"
    GEMINI_2_5_FLASH = "gemini-2.5-flash"
    GPT_4O = "gpt-4o"
    QWEN_2_5_VL = "qwen2.5-vl"
    HUMAN = "human"


class Criterion(CrucibleModel):
    id: str
    description: str
    type: CriterionType
    weight: float = Field(ge=0)
    hard_gate: bool
    expected: dict[str, Any] | str | float | int | bool | None = None
    evaluator: EvaluatorKind | str


class Rubric(CrucibleModel):
    criteria: list[Criterion] = Field(min_length=1)

    @field_validator("criteria")
    @classmethod
    def criterion_ids_must_be_unique(cls, criteria: list[Criterion]) -> list[Criterion]:
        ids = [criterion.id for criterion in criteria]
        if len(ids) != len(set(ids)):
            raise ValueError("criterion ids must be unique")
        return criteria

    def by_id(self, criterion_id: str) -> Criterion:
        for criterion in self.criteria:
            if criterion.id == criterion_id:
                return criterion
        raise KeyError(criterion_id)


def load_rubric(path: Path) -> Rubric:
    try:
        import yaml
    except ImportError as exc:
        raise RuntimeError("PyYAML is required to load rubrics.") from exc

    with path.open("r", encoding="utf-8") as handle:
        loaded = yaml.safe_load(handle) or {}
    return Rubric.model_validate(loaded)
