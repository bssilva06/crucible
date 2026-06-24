from __future__ import annotations

from io import BytesIO
from pathlib import Path

import pytest
from PIL import Image
from pydantic import ValidationError

from crucible.checks.deterministic import run_deterministic_checks
from crucible.domain.evaluation import evaluation_status, failed_hard_gates
from crucible.domain.rubric import Rubric, load_rubric
from crucible.phase0.crypto import sha256_bytes


RUBRIC_PATH = Path("configs/rubrics/ecommerce-product-shot.yaml")


def test_rubric_loads() -> None:
    rubric = load_rubric(RUBRIC_PATH)

    assert [criterion.id for criterion in rubric.criteria] == [
        "file_integrity",
        "minimum_resolution",
        "aspect_ratio",
        "white_background_edges",
    ]


def test_duplicate_criterion_ids_are_rejected() -> None:
    rubric = load_rubric(RUBRIC_PATH)
    data = rubric.model_dump()
    data["criteria"][1]["id"] = "file_integrity"

    with pytest.raises(ValidationError):
        Rubric.model_validate(data)


def test_white_square_image_passes_all_deterministic_checks() -> None:
    image_bytes = _png_bytes(width=512, height=512, color=(255, 255, 255))
    results = _run(image_bytes)

    assert all(result.passed for result in results)
    assert evaluation_status(results) == "PASSED"


def test_corrupt_bytes_fail_file_integrity_and_downstream_checks() -> None:
    results = _run(b"not-an-image")

    assert results[0].criterion_id == "file_integrity"
    assert results[0].passed is False
    assert failed_hard_gates(results) == [
        "file_integrity",
        "minimum_resolution",
        "aspect_ratio",
        "white_background_edges",
    ]


def test_below_minimum_image_fails_resolution() -> None:
    results = _run(_png_bytes(width=64, height=64, color=(255, 255, 255)))

    assert _by_id(results, "file_integrity").passed is True
    assert _by_id(results, "minimum_resolution").passed is False
    assert "minimum_resolution" in failed_hard_gates(results)


def test_non_square_image_fails_aspect_ratio() -> None:
    results = _run(_png_bytes(width=800, height=512, color=(255, 255, 255)))

    assert _by_id(results, "minimum_resolution").passed is True
    assert _by_id(results, "aspect_ratio").passed is False
    assert "aspect_ratio" in failed_hard_gates(results)


def test_non_white_edges_fail_background_check() -> None:
    results = _run(_png_bytes(width=512, height=512, color=(0, 0, 0)))

    assert _by_id(results, "white_background_edges").passed is False
    assert "white_background_edges" in failed_hard_gates(results)


def _run(image_bytes: bytes):
    return run_deterministic_checks(
        asset_bytes=image_bytes,
        mime_type="image/png",
        asset_uri="b2://local/test.png",
        asset_sha256=sha256_bytes(image_bytes),
        rubric=load_rubric(RUBRIC_PATH),
    )


def _png_bytes(*, width: int, height: int, color: tuple[int, int, int]) -> bytes:
    image = Image.new("RGB", (width, height), color)
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def _by_id(results, criterion_id: str):
    return next(result for result in results if result.criterion_id == criterion_id)
