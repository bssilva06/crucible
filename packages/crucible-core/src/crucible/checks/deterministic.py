from __future__ import annotations

from io import BytesIO

from PIL import Image, UnidentifiedImageError

from crucible.domain.evaluation import CriterionResult
from crucible.domain.rubric import Criterion, CriterionType, EvaluatorKind, Rubric


def run_deterministic_checks(
    *,
    asset_bytes: bytes,
    mime_type: str,
    asset_uri: str,
    asset_sha256: str,
    rubric: Rubric,
) -> list[CriterionResult]:
    image: Image.Image | None = None
    decode_error: str | None = None
    results: list[CriterionResult] = []

    for criterion in rubric.criteria:
        if criterion.type == CriterionType.FILE_INTEGRITY:
            try:
                image = Image.open(BytesIO(asset_bytes))
                image.load()
                results.append(
                    _result(
                        criterion,
                        passed=True,
                        score=1.0,
                        feedback="Image decoded successfully.",
                        evidence={
                            "asset_uri": asset_uri,
                            "asset_sha256": asset_sha256,
                            "mime_type": mime_type,
                            "width": image.width,
                            "height": image.height,
                        },
                    )
                )
            except (UnidentifiedImageError, OSError, ValueError) as exc:
                decode_error = str(exc)
                results.append(
                    _result(
                        criterion,
                        passed=False,
                        score=0.0,
                        feedback="Asset bytes did not decode as an image.",
                        evidence={
                            "asset_uri": asset_uri,
                            "asset_sha256": asset_sha256,
                            "mime_type": mime_type,
                            "error": decode_error,
                        },
                    )
                )
        elif criterion.type == CriterionType.RESOLUTION:
            results.append(_resolution_result(criterion, image, decode_error))
        elif criterion.type == CriterionType.ASPECT_RATIO:
            results.append(_aspect_ratio_result(criterion, image, decode_error))
        elif criterion.type == CriterionType.PIXEL_BACKGROUND_CHECK:
            results.append(_white_edge_result(criterion, image, decode_error))

    return results


def _resolution_result(criterion: Criterion, image: Image.Image | None, decode_error: str | None) -> CriterionResult:
    if image is None:
        return _blocked_result(criterion, decode_error)

    expected = _expected_dict(criterion)
    min_width = int(expected.get("min_width", 512))
    min_height = int(expected.get("min_height", 512))
    passed = image.width >= min_width and image.height >= min_height
    score = min(min(image.width / min_width, image.height / min_height), 1.0)
    return _result(
        criterion,
        passed=passed,
        score=score,
        feedback=(
            f"Image resolution is {image.width}x{image.height}; required at least {min_width}x{min_height}."
        ),
        evidence={
            "width": image.width,
            "height": image.height,
            "min_width": min_width,
            "min_height": min_height,
        },
    )


def _aspect_ratio_result(criterion: Criterion, image: Image.Image | None, decode_error: str | None) -> CriterionResult:
    if image is None:
        return _blocked_result(criterion, decode_error)

    expected = _expected_dict(criterion)
    target_ratio = float(expected.get("ratio", 1.0))
    tolerance = float(expected.get("tolerance", 0.02))
    actual_ratio = image.width / image.height
    delta = abs(actual_ratio - target_ratio)
    passed = delta <= tolerance
    score = max(0.0, 1.0 - (delta / max(tolerance, 0.0001)))
    return _result(
        criterion,
        passed=passed,
        score=score,
        feedback=f"Image aspect ratio is {actual_ratio:.4f}; target is {target_ratio:.4f}.",
        evidence={
            "width": image.width,
            "height": image.height,
            "actual_ratio": actual_ratio,
            "target_ratio": target_ratio,
            "tolerance": tolerance,
            "delta": delta,
        },
    )


def _white_edge_result(criterion: Criterion, image: Image.Image | None, decode_error: str | None) -> CriterionResult:
    if image is None:
        return _blocked_result(criterion, decode_error)

    expected = _expected_dict(criterion)
    required_pass_rate = float(expected.get("edge_pass_rate", 0.95))
    tolerance = int(expected.get("rgb_tolerance", 18))
    rgb = image.convert("RGB")
    edge_pixels = _edge_pixels(rgb)
    passing = sum(1 for pixel in edge_pixels if _is_white(pixel, tolerance))
    pass_rate = passing / len(edge_pixels) if edge_pixels else 0.0
    passed = pass_rate >= required_pass_rate
    return _result(
        criterion,
        passed=passed,
        score=pass_rate,
        feedback=f"White edge pass rate is {pass_rate:.3f}; required at least {required_pass_rate:.3f}.",
        evidence={
            "edge_pixel_count": len(edge_pixels),
            "passing_edge_pixels": passing,
            "edge_pass_rate": pass_rate,
            "required_edge_pass_rate": required_pass_rate,
            "rgb_tolerance": tolerance,
        },
    )


def _edge_pixels(image: Image.Image) -> list[tuple[int, int, int]]:
    width, height = image.size
    pixels = image.load()
    values: list[tuple[int, int, int]] = []
    for x in range(width):
        values.append(pixels[x, 0])
        if height > 1:
            values.append(pixels[x, height - 1])
    for y in range(1, max(height - 1, 1)):
        values.append(pixels[0, y])
        if width > 1:
            values.append(pixels[width - 1, y])
    return values


def _is_white(pixel: tuple[int, int, int], tolerance: int) -> bool:
    return all(channel >= 255 - tolerance for channel in pixel)


def _blocked_result(criterion: Criterion, decode_error: str | None) -> CriterionResult:
    return _result(
        criterion,
        passed=False,
        score=0.0,
        feedback="Check could not run because image decoding failed.",
        evidence={"decode_error": decode_error or "unknown"},
    )


def _result(
    criterion: Criterion,
    *,
    passed: bool,
    score: float,
    feedback: str,
    evidence: dict[str, object],
) -> CriterionResult:
    return CriterionResult(
        criterion_id=criterion.id,
        passed=passed,
        score=max(0.0, min(score, 1.0)),
        hard_gate=criterion.hard_gate,
        evaluator=EvaluatorKind.DETERMINISTIC,
        feedback=feedback,
        evidence=evidence,
    )


def _expected_dict(criterion: Criterion) -> dict[str, object]:
    return criterion.expected if isinstance(criterion.expected, dict) else {}
