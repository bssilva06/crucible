# Crucible Pydantic Domain Models

This artifact defines the core Pydantic v2 domain models for Crucible. The models are designed around the PRD's main invariants:

- One run contains one or more generation rounds.
- One round contains multiple candidate attempts.
- A winner is identified by `attempt_id`, not by iteration alone.
- `quality_score` and `judge_confidence` are separate concepts.
- Hallmarks are append-only certification records layered on top of Genblaze manifests.
- Failed runs may have no winner, ranking, gold audit, or asset hash.

## Suggested File

```text
packages/crucible-core/src/crucible/domain/models.py
```

## Model Code

```python
from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, field_validator, model_validator


class CrucibleModel(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        frozen=False,
        populate_by_name=True,
        validate_assignment=True,
    )


class HallmarkStatus(StrEnum):
    CERTIFIED = "CERTIFIED"
    NEEDS_REVIEW = "NEEDS_REVIEW"
    FAILED = "FAILED"


class CandidateStatus(StrEnum):
    GENERATED = "GENERATED"
    REJECTED = "REJECTED"
    ELIGIBLE = "ELIGIBLE"
    SELECTED = "SELECTED"


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


class JudgeRole(StrEnum):
    LIVE = "live"
    ADJUDICATOR = "adjudicator"
    GOLD = "gold"


class RiskScreeningStatus(StrEnum):
    CLEAR = "clear"
    WARNING = "warning"
    BLOCKED = "blocked"


class C2PAStatus(StrEnum):
    NOT_EMBEDDED = "not_embedded"
    EMBEDDED = "embedded"


class AssetRef(CrucibleModel):
    uri: str = Field(description="Storage URI, commonly b2://...")
    sha256: str | None = Field(default=None, min_length=64, max_length=64)
    mime_type: str | None = None
    width: int | None = Field(default=None, ge=1)
    height: int | None = Field(default=None, ge=1)
    bytes_size: int | None = Field(default=None, ge=0)


class Brief(CrucibleModel):
    brief_id: str
    prompt: str = Field(min_length=1)
    vertical: str = "ecommerce_product_shot"
    required_text: list[str] = Field(default_factory=list)
    brand_guidelines: dict[str, Any] = Field(default_factory=dict)
    constraints: dict[str, Any] = Field(default_factory=dict)
    locale: str | None = None


class CriterionNormalization(CrucibleModel):
    case_sensitive: bool | None = None
    collapse_whitespace: bool | None = None
    trim: bool | None = None
    locale: str | None = None


class Criterion(CrucibleModel):
    id: str
    description: str
    type: CriterionType
    weight: float = Field(ge=0)
    hard_gate: bool
    expected: Any | None = None
    evaluator: EvaluatorKind | str
    normalization: CriterionNormalization | dict[str, Any] | None = None


class Rubric(CrucibleModel):
    criteria: list[Criterion] = Field(min_length=1)

    @field_validator("criteria")
    @classmethod
    def criterion_ids_must_be_unique(cls, criteria: list[Criterion]) -> list[Criterion]:
        ids = [criterion.id for criterion in criteria]
        if len(ids) != len(set(ids)):
            raise ValueError("criterion ids must be unique")
        return criteria


class ProviderInfo(CrucibleModel):
    provider: str
    model: str
    family: str | None = None
    model_revision: str | None = None
    provider_request_id: str | None = None
    response_timestamp: datetime | None = None


class GenerationParameters(CrucibleModel):
    seed: int | None = None
    width: int | None = Field(default=None, ge=1)
    height: int | None = Field(default=None, ge=1)
    steps: int | None = Field(default=None, ge=1)
    guidance_scale: float | None = Field(default=None, ge=0)
    raw: dict[str, Any] = Field(default_factory=dict)


class CriterionResult(CrucibleModel):
    criterion_id: str
    passed: bool
    score: float | None = Field(default=None, ge=0, le=1)
    hard_gate: bool
    evaluator: EvaluatorKind | str
    feedback: str | None = None
    evidence: dict[str, Any] = Field(default_factory=dict)
    evaluated_at: datetime = Field(default_factory=datetime.utcnow)


class Candidate(CrucibleModel):
    attempt_id: str
    candidate_index: int = Field(ge=0)
    iteration: int = Field(ge=0)
    prompt: str
    provider: ProviderInfo
    asset: AssetRef
    generation_parameters: GenerationParameters = Field(default_factory=GenerationParameters)
    status: CandidateStatus = CandidateStatus.GENERATED
    eligible: bool = False
    failed_hard_gates: list[str] = Field(default_factory=list)
    criterion_results: list[CriterionResult] = Field(default_factory=list)

    @model_validator(mode="after")
    def eligibility_matches_failed_gates(self) -> Candidate:
        if self.failed_hard_gates and self.eligible:
            raise ValueError("candidate cannot be eligible while failed_hard_gates is non-empty")
        return self


class GenblazeRoundRef(CrucibleModel):
    run_id: str
    parent_run_id: str | None = None
    manifest_uri: str


class CandidateBundle(CrucibleModel):
    iteration: int = Field(ge=0)
    prompt: str
    genblaze: GenblazeRoundRef | None = None
    candidates: list[Candidate] = Field(min_length=1)

    @model_validator(mode="after")
    def candidates_match_iteration(self) -> CandidateBundle:
        mismatched = [candidate.attempt_id for candidate in self.candidates if candidate.iteration != self.iteration]
        if mismatched:
            raise ValueError(f"candidate iteration mismatch: {mismatched}")
        return self


class PairwiseComparison(CrucibleModel):
    comparison_id: str
    criterion_ids: list[str] = Field(default_factory=list)
    left_attempt_id: str
    right_attempt_id: str
    winner_attempt_id: str | None = None
    judge: EvaluatorKind | str
    order: Literal["forward", "reverse"]
    reasoning_sha256: str | None = Field(default=None, min_length=64, max_length=64)
    score_margin: float | None = Field(default=None, ge=0, le=1)

    @model_validator(mode="after")
    def winner_must_be_candidate_or_tie(self) -> PairwiseComparison:
        if self.winner_attempt_id is not None and self.winner_attempt_id not in {
            self.left_attempt_id,
            self.right_attempt_id,
        }:
            raise ValueError("winner_attempt_id must match left_attempt_id, right_attempt_id, or be null for tie")
        return self


class RankingSummary(CrucibleModel):
    method: Literal["bidirectional_pairwise_tournament"]
    eligible_attempt_ids: list[str]
    winner_attempt_id: str
    comparison_count: int = Field(ge=0)
    comparisons_uri: str | None = None
    order_symmetry: float | None = Field(default=None, ge=0, le=1)
    ranking_margin: float | None = Field(default=None, ge=0, le=1)

    @model_validator(mode="after")
    def winner_must_be_eligible(self) -> RankingSummary:
        if self.winner_attempt_id not in self.eligible_attempt_ids:
            raise ValueError("ranking winner must be one of the eligible attempts")
        return self


class ConfidenceBreakdown(CrucibleModel):
    order_symmetry: float | None = Field(default=None, ge=0, le=1)
    ensemble_agreement: float | None = Field(default=None, ge=0, le=1)
    criterion_consistency: float | None = Field(default=None, ge=0, le=1)
    ranking_margin: float | None = Field(default=None, ge=0, le=1)
    pre_adjudication_confidence: float = Field(ge=0, le=1)
    final_confidence: float = Field(ge=0, le=1)
    qwen_invoked: bool = False


class RoundVerdict(CrucibleModel):
    passed: bool
    selected_attempt_id: str | None = None
    quality_score: float = Field(ge=0, le=1)
    confidence: float = Field(ge=0, le=1)
    feedback: str
    criterion_failures: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def selected_attempt_required_when_passed(self) -> RoundVerdict:
        if self.passed and self.selected_attempt_id is None:
            raise ValueError("selected_attempt_id is required when verdict passed is true")
        return self


class JudgeRecord(CrucibleModel):
    role: JudgeRole
    model: str
    family: str
    version: str | None = None
    qwen_invoked: bool | None = None


class GoldAudit(CrucibleModel):
    role: Literal[JudgeRole.GOLD] = JudgeRole.GOLD
    model: str
    family: str
    agreement: bool
    score: float | None = Field(default=None, ge=0, le=1)
    feedback: str | None = None
    evaluated_at: datetime = Field(default_factory=datetime.utcnow)


class IPRiskScreening(CrucibleModel):
    status: RiskScreeningStatus
    signals: list[str] = Field(default_factory=list)
    legal_determination: Literal[False] = False


class LLMCallRecord(CrucibleModel):
    purpose: Literal["rubric_compile", "prompt_rewrite", "judge", "gold_audit", "other"]
    model: str
    version: str | None = None
    input_prompt_sha256: str = Field(min_length=64, max_length=64)
    output_sha256: str = Field(min_length=64, max_length=64)
    tokens: dict[str, int] = Field(default_factory=dict)
    cost_usd: float | None = Field(default=None, ge=0)
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    parent_iteration: int | None = Field(default=None, ge=0)


class StoragePolicy(CrucibleModel):
    provider: Literal["backblaze_b2"]
    object_lock_requested: bool
    requested_mode: Literal["governance", "compliance"] | None = None
    requested_retention_days: int | None = Field(default=None, ge=1)


class StorageReceipt(CrucibleModel):
    provider: Literal["backblaze_b2"]
    bucket: str
    key: str
    version_id: str | None = None
    object_lock_mode: str | None = None
    retain_until: datetime | None = None
    observed_at: datetime = Field(default_factory=datetime.utcnow)


class C2PARecord(CrucibleModel):
    status: C2PAStatus = C2PAStatus.NOT_EMBEDDED
    assertion: str | None = None
    manifest_store_hash: str | None = None


class IntegrityRecord(CrucibleModel):
    canonicalization: Literal["RFC8785"] = "RFC8785"
    hashed_fields_exclude: list[str] = Field(
        default_factory=lambda: [
            "integrity.hallmark_sha256",
            "integrity.cryptographic_signature",
        ]
    )
    asset_sha256: str | None = Field(default=None, min_length=64, max_length=64)
    hallmark_sha256: str | None = Field(default=None, min_length=64, max_length=64)
    cryptographic_signature: dict[str, Any] | None = None
    c2pa: C2PARecord = Field(default_factory=C2PARecord)


class WinnerRecord(CrucibleModel):
    attempt_id: str
    iteration: int = Field(ge=0)
    rank_method: Literal["pairwise"]
    judge_confidence: float = Field(ge=0, le=1)


class HallmarkIssuer(CrucibleModel):
    name: str = "Crucible"
    version: str


class HallmarkRound(CrucibleModel):
    iteration: int = Field(ge=0)
    refined_prompt_sha256: str = Field(min_length=64, max_length=64)
    genblaze: GenblazeRoundRef
    candidates: list[Candidate] = Field(min_length=1)


class Hallmark(CrucibleModel):
    schema_version: str = "1.0.0"
    status: HallmarkStatus
    issued_at: datetime = Field(default_factory=datetime.utcnow)
    issuer: HallmarkIssuer

    run_id: str
    manifest_uri: str
    rubric: Rubric
    rounds: list[HallmarkRound] = Field(min_length=1)

    ranking: RankingSummary | None = None
    winner: WinnerRecord | None = None
    judge: JudgeRecord | None = None
    gold_audit: GoldAudit | None = None
    within_run_diversity_index: float | None = Field(default=None, ge=0, le=1)

    ip_risk_screening: IPRiskScreening | None = None
    llm_calls: list[LLMCallRecord] = Field(default_factory=list)
    storage_policy: StoragePolicy
    integrity: IntegrityRecord

    @model_validator(mode="after")
    def outcome_fields_match_status(self) -> Hallmark:
        if self.status == HallmarkStatus.FAILED:
            forbidden = {
                "winner": self.winner,
                "ranking": self.ranking,
                "gold_audit": self.gold_audit,
                "asset_sha256": self.integrity.asset_sha256,
            }
            present = [name for name, value in forbidden.items() if value is not None]
            if present:
                raise ValueError(f"FAILED Hallmark must not include: {present}")
            return self

        required = {
            "winner": self.winner,
            "gold_audit": self.gold_audit,
            "asset_sha256": self.integrity.asset_sha256,
        }
        missing = [name for name, value in required.items() if value is None]
        if missing:
            raise ValueError(f"{self.status} Hallmark is missing required fields: {missing}")

        if self.ranking is not None and self.winner is not None:
            if self.ranking.winner_attempt_id != self.winner.attempt_id:
                raise ValueError("ranking winner and Hallmark winner must match")

        return self


class HallmarkRevocation(CrucibleModel):
    type: Literal["hallmark_revocation"] = "hallmark_revocation"
    revoked_hallmark_sha256: str = Field(min_length=64, max_length=64)
    reason: str = Field(min_length=1)
    issued_at: datetime = Field(default_factory=datetime.utcnow)
```

## Genblaze Adapter Boundary

Crucible should adapt `RoundVerdict` into Genblaze's `EvaluationResult` at the integration edge:

```python
def to_genblaze_evaluation_result(verdict: RoundVerdict):
    from genblaze import EvaluationResult

    return EvaluationResult(
        passed=verdict.passed,
        score=verdict.quality_score,
        feedback=verdict.feedback,
    )
```

Do not expose Genblaze objects throughout the domain model. Keep them at the orchestration boundary so the core evaluator, Hallmark verifier, and validation harness can be tested without provider calls.

## Model Split Recommendation

Once this grows, split `models.py` into:

```text
domain/
  base.py
  brief.py
  rubric.py
  candidate.py
  ranking.py
  judge.py
  hallmark.py
  storage.py
```

Keep cross-model validators close to the aggregate root they protect. For example, Hallmark outcome validation belongs on `Hallmark`, not on `WinnerRecord`.

## Important Validation Rules Captured

| Rule | Model |
|---|---|
| Criterion IDs are unique within a rubric. | `Rubric` |
| Candidate cannot be eligible while hard gates failed. | `Candidate` |
| Candidate iteration must match its bundle iteration. | `CandidateBundle` |
| Pairwise winner must be left, right, or null. | `PairwiseComparison` |
| Ranking winner must be eligible. | `RankingSummary` |
| Passed verdict requires selected attempt. | `RoundVerdict` |
| Failed Hallmark has no winner, ranking, gold audit, or asset hash. | `Hallmark` |
| Certified/needs-review Hallmark requires winner, gold audit, and asset hash. | `Hallmark` |
| Ranking winner and Hallmark winner must match. | `Hallmark` |
| IP-risk screening cannot claim legal determination. | `IPRiskScreening` |

## Deliberately Loose Fields

Some fields are intentionally `dict[str, Any]` or `str`-based for v1:

- Provider-specific generation parameters vary across GMICloud, Replicate, Imagen, and future adapters.
- Criterion `expected` values differ by criterion type.
- Judge evidence may include OCR spans, bounding boxes, VLM rationales, or safety classifier metadata.
- Cryptographic signatures and C2PA implementation details are stretch goals.

These can become discriminated unions after the first working pipeline reveals the real shapes.
