# Crucible — Product Requirements Document

**An adversarial generate-and-certify gauntlet for AI media, built on Genblaze + Backblaze B2.**

| | |
|---|---|
| **Author** | Ben |
| **Hackathon** | Backblaze Generative Media Hackathon: Build with Genblaze on B2 |
| **Submission deadline** | Aug 3, 2026, 5:00pm EDT |
| **Status** | Draft v1.0 |
| **One-liner** | Genblaze gives you the loop and the receipt; Crucible builds the judge and the verdict. |

---

## 1. TL;DR

Crucible turns a creative brief into a *certified* media asset. It fans out generation across multiple providers via Genblaze, runs an adversarial multi-criteria VLM judge over every candidate, selects or iteratively refines until the output clears a quality/safety bar, and writes a tamper-evident **Hallmark evaluation record** — and, for passing assets, a **certified Hallmark** — to Backblaze B2, capturing the full QC trajectory plus provenance.

The wedge: Genblaze already ships the generate→evaluate→retry loop (`AgentLoop`) and provenance (`Manifest`), but it leaves the **evaluator a stub** ("replace this with your own scorer"). The evaluator — the brain that decides whether an output is good and *can't be gamed* — is the hard, valuable part, and it's exactly what Crucible builds.

**Why now:** EU AI Act Article 50 enforcement begins **Aug 2, 2026** — one day before the submission deadline — mandating machine-readable provenance for AI media. Crucible's certified-provenance output is a direct answer.

---

## 2. Problem

Teams that put AI media into production hit four documented pains:

1. **The re-prompt loop.** Generate → it's off → tweak → regenerate. Each cycle burns 15–30 minutes, and pro workflows need 3–10 iterations per final asset. Automating away this manual labor is the core value.
2. **QC doesn't scale.** Human review and standalone testing are expensive and only cover a fraction of output.
3. **Asset/version chaos.** Thousands of generation iterations, no version control, no brand-safety gate, no audit trail.
4. **Compliance gap.** "We used ChatGPT" is not an audit trail. As of Aug 2, 2026, EU-facing AI media legally requires machine-readable provenance.

**The market gap (from research):** the generate→judge→retry *algorithm* is proven in research; multi-model *human-pick* comparison tools exist (MultipleChat, Cutout.pro); enterprise auto-QC exists only internally (Amazon Catalog AI) and for text. **No open, developer-facing pipeline combines multi-provider generation + automated brief-aware judging + auto-refinement + durable certified provenance.** That's Crucible.

---

## 3. What Genblaze gives vs. what Crucible builds

| Capability | Ships in Genblaze | Crucible adds |
|---|---|---|
| Generate→evaluate→retry loop | ✅ `AgentLoop` | The evaluator that plugs into it |
| Provenance record | ✅ `Manifest` (SHA-256, embeddable) | Quality/safety certification on top (Hallmark) |
| Failure retry | ✅ `fallback_models` (on `MODEL_ERROR`) | **Quality**-based routing + best-of-N selection |
| Multi-provider | ✅ 11 adapters, one `Pipeline` API | Per-criterion routing policy |
| Durable storage | ✅ `ObjectStorageSink` to B2 | Certified-record data model + Object Lock + Parquet eval tables |
| Run lineage | ✅ `parent_run_id`, `from_result()` | Full eval trajectory (every attempt, score, rejection reason) |

> The Genblaze `AgentLoop` example literally says: *"Replace this with your own scorer — a vision model call, a classifier, or any function that returns a score between 0.0 and 1.0."* That blank is the project.

---

## 4. Research foundation → design decisions

Every core design choice is grounded in the literature (full links in §14).

| Finding | Source | Design decision in Crucible |
|---|---|---|
| VLM judges **rank well but score poorly** (ranking-scoring decoupling) | *VLM Judges Can Rank but Cannot Score* (2026) | Select by **pairwise/tournament ranking**, not an absolute 0–1 threshold |
| **Position bias** ~5% persists even with instructions | WebDevJudge / PairBench (2025) | Randomize candidate order; average both directions; report symmetry |
| **Self-preference** (egocentric bias) | MLLM-as-a-Judge (2024) | **Cross-family judge** (don't let a model in the generation set be the gate) |
| **Text-in-image** is a VLM weak spot | ABHINAW (2024); Ideogram is the text model | **Dedicated OCR check** for legibility, not the VLM |
| **Iterative refinement beats compute-matched best-of-N** for compositional prompts (+17% ConceptMix; humans prefer 58.7/41.3) | *Iterative Refinement Improves Compositional Image Generation* (2026) | **Hybrid**: best-of-N for simple briefs; iterative refinement (prompt-rewrite + memory, capped) for hard ones |
| Refinement needs a **general critic + memory**, no artifact-inducing tools | Test-time Prompt Refinement (2025) | Keep critic general; carry full attempt+feedback history into the rewrite |
| **Goodhart is structural**: proxy-true gap grows with optimization strength | Gao et al. scaling laws | **Cap N and iterations** as a principled defense, not just for cost |
| **Best-of-N has lower hackability** than gradient/noise optimization | MIRA (2025) | Crucible uses BoN selection + prompt feedback, *not* gradient/noise optimization |
| **Ensembling partially mitigates** hacking but shares error patterns | T2I reward-hacking study (2026) | Cross-family ensemble for the gate; do not assume it eliminates hacking |
| **Benchmark drift**: auto-eval diverges from humans up to 17.7% as models improve | GenEval 2 (2025) | Treat the judge as a **governed artifact**; re-anchor to fresh human labels periodically |
| **Quality leadership rotates quarterly**; cost leadership stable | Digital Applied API comparison (2026) | **Config-driven model registry**, not a learned router; two-provider stack |

---

## 5. Tech stack & model selection

### Decision summary

| Layer | Choice | Why |
|---|---|---|
| Language / runtime | **Python 3.11+** | Required by Genblaze |
| Orchestration | **Genblaze** (`genblaze-core` + adapters) | Hackathon requirement; ships the loop, manifest, routing primitives |
| Storage | **Backblaze B2** via `genblaze-s3` | Hackathon requirement; Object Lock for certs |
| Generation — core #1 | **GMICloud** (Seedream, FLUX) | Credit-backed by the hackathon; native Genblaze adapter; in normal fan-out |
| Generation — core #2 | **Replicate** (Flux, SDXL) | Cheap, broad; in normal fan-out alongside GMICloud |
| Generation — premium (fallback only) | **Google Imagen 4** (`genblaze-google`) | Clean license, strong photorealism; invoked only after a quality miss, *not* in normal fan-out |
| Live judge | **Gemini 2.5 Flash** | ~0.82 human correlation, ~36× cheaper than Claude, fast |
| Gold judge (cross-family) | **GPT-4o** | Different family → detects self-preference & reward hacking |
| Ensemble member / OCR-leaning | **Qwen2.5-VL** (via GMICloud) | Credit-backed; top open-weight OCR; third family |
| Text legibility | **PaddleOCR** | VLM-independent (research requirement); EN/ES for the bilingual path |
| Eval analytics | **DuckDB** over Genblaze `ParquetSink` | Fast local SQL on eval tables for κ + metrics |
| Observability | Genblaze `OTelTracer` (+ `LoggingTracer` locally) | Native; export to a free Honeycomb/Jaeger tier if useful |
| Backend | **FastAPI** (async), embeds Genblaze | Library-only SDK embeds cleanly; SSE for live progress |
| Frontend | **Next.js (React + TS) + Tailwind** | Custom gauntlet dashboard; consumes `@genblaze/spec` TS types |
| App metadata / auth (optional) | **Supabase (Postgres)** | Run index + auth if multi-user; B2 stays source of truth |
| Backend deploy | **Modal** (fallback: Railway) | Serverless Python; built for bursty long-running media jobs (listed in Genblaze docs) |
| Frontend deploy | **Vercel** | Next.js native; public URL for judges |

### Rationale (grounded in the research)

**Judge ensemble is cross-family by design.** Per-model human-correlation numbers: Claude 3.5 Sonnet / Gemini ~0.82–0.83, GPT-4o ~0.80, Qwen2.5-VL ~0.75 — and an ensemble of all of them reaches ~0.85, beating any single judge. Since Claude isn't a Genblaze adapter, the accessible-via-`chat()` ensemble is **Gemini 2.5 Flash + GPT-4o + Qwen2.5-VL**: the strongest available combination *and* three distinct families. The live gate uses Gemini (cheap, fast); the gold audit uses GPT-4o (inline per-asset agreement check, plus an offline diversity monitor across runs); Qwen adds OCR-leaning strength. **Cross-family hygiene rule:** never let a generator be judged solely by its own family (e.g., when generating with Imagen, down-weight the Gemini judge).

**Text gets OCR, not the VLM.** Legibility is a known VLM weak spot, so PaddleOCR checks rendered text against the brief's required strings letter-by-letter. It's VLM-independent (satisfies the design requirement) and multilingual, which also seeds the bilingual border-SMB extension.

**Two core providers + an on-demand premium fallback, config-routed.** Because quality leadership rotates quarterly while cost leadership is stable, Crucible avoids a learned router. The normal fan-out runs across **two core providers — GMICloud (credit-backed) and Replicate (cheap, broad)**. **Imagen 4 is a premium fallback invoked only after a quality miss on the core providers**, not part of the standard fan-out. All three are swappable through Genblaze's `ModelRegistry` without code changes.

**TypeScript frontend is doc-justified.** Genblaze publishes `@genblaze/spec` on npm — generated `.d.ts` types for the manifest/cert schema — so a Next.js/TS frontend stays type-synced with the Python models. That makes React the *lower-risk* frontend choice here, not just the familiar one.

**Async backend for long jobs.** Media generation runs seconds to minutes (video longer), so the backend uses Genblaze's async/streaming runners (`arun`/`astream`) behind FastAPI, surfacing live gauntlet progress to the UI over SSE. Modal is the deploy target — serverless Python suited to bursty, long-running jobs and explicitly listed among Genblaze's supported runtimes.

### Time-box fallback

If the schedule tightens, collapse frontend + backend into a single **Gradio (or Streamlit)** app on Hugging Face Spaces — Python-only, embeds Genblaze directly, one deploy. Trades dashboard polish for speed, still yields a public app URL for judges.

---

## 6. Solution architecture

```
Brief ──► Rubric Compiler ──► [weighted checklist]
                                     │
                          ┌──────────┴───────────┐
                          ▼                        ▼
                  Generation fan-out        Routing policy
              (Genblaze parallel/BoN     (per-criterion model
               across providers)          strengths, cost/latency)
                          │
                          ▼
                  Candidates (N)
                          │
        ┌─────────────────┼──────────────────┐
        ▼                 ▼                   ▼
  VLM judge          OCR check          Safety/brand check
 (cross-family,     (text legibility)   (NSFW / IP risk)
  pairwise rank)
        └─────────────────┼──────────────────┘
                          ▼
                  Verdict aggregator
                   │            │
            PASS ──┘            └── FAIL
              │                       │
              ▼                       ▼
       Hallmark cert         Iterative refinement
       + Genblaze manifest   (rewrite prompt w/ memory,
       + (opt) C2PA assertion   reroute model) — capped
              │                       │
              ▼                       └──► back to fan-out
        Backblaze B2
   (Object Lock, content-addressable,
    Parquet eval tables)
              │
              ▼
   Gold-judge audit + diversity monitor
   (reward-hacking detection, offline)
```

### Component spec

- **Rubric Compiler.** Brief → weighted, checkable criteria. Decompose into TIFA-style yes/no visual questions (objective items: object present, count, color, spatial, aspect ratio, white background) + subjective items (on-brand, premium look) with lower weight. Implemented as an LLM call via Genblaze's `chat()`. *Logged to the Hallmark `llm_calls` block (see §7) — `chat()` is not a Pipeline citizen, so Genblaze's manifest will not capture it automatically.*
- **Generation fan-out.** Genblaze `Pipeline` parallel execution / `batch_run` across the **core providers** (GMICloud + Replicate). `N` configurable (default 4), capped at 8.
- **Routing policy.** Config table mapping criteria → model strengths (e.g. text → Flux; photorealism → Imagen), with quality/cost/latency weights. Backed by Genblaze `ModelRegistry`. The **premium fallback (Imagen 4)** is invoked only after a quality miss on the core providers, *not* in the normal fan-out.
- **Deterministic checks.** Free, VLM-independent gates run first: aspect ratio, resolution, file integrity, transparency/background where applicable. Fail-fast to avoid spending judge calls on disqualified candidates.
- **OCR check.** **PaddleOCR** compares rendered text to the brief's required strings letter-by-letter; the VLM does not adjudicate legibility. EN/ES capable for the bilingual extension.
- **Judge (the IP).** Cross-family VLM (live: Gemini 2.5 Flash), pairwise/tournament ranking over the *eligible* candidates, order randomized + averaged. Returns the Genblaze `EvaluationResult(passed, score, feedback)` the `AgentLoop` consumes. Confidence estimate gates human escalation. *Judge model + version logged to the Hallmark.*
- **Safety, brand & IP-risk screening.** A separate pass flags NSFW content, brand-guide violations, and possible third-party logos/characters. Output is a **warning with signals, not a legal determination** — the VLM can flag a suspected logo, it cannot adjudicate infringement (see `ip_risk_screening` in §7).
- **Verdict aggregator.** Weighted combination; objective criteria are hard gates (a candidate failing one is removed before ranking), subjective ones are soft.
- **Refinement loop.** On fail: rewrite the full prompt (not naive append) using the accumulated attempt+feedback memory, optionally reroute model based on *why* it failed. Capped at 3 iterations. *Each rewrite logged to the Hallmark `llm_calls` block.*
- **Gold-judge audit.** Inline per-asset: a single cross-family judge (GPT-4o) re-scores the winner; agreement recorded in the cert. Offline aggregate: a diversity monitor across many runs flags collapse. Divergence between live and gold judge, rising with optimization pressure, is the reward-hacking signal.

### Pipeline sequence

The order is load-bearing — hard gates filter *before* ranking, so the winner is the best *eligible* candidate, not the best-looking one that fails a gate. Cheap checks run before expensive ones to avoid wasted judge calls.

```
1.  Generate N candidates (core providers)
2.  Deterministic checks         # free; fail-fast
3.  OCR check                    # cheap; PaddleOCR
4.  Safety, brand & IP-risk screening   # cheap NSFW gate first — reject before paying for the VLM
5.  VLM criterion checks         # the judge, per criterion
6.  Remove candidates failing any HARD GATE
7.  Pairwise-rank remaining (eligible) candidates
8.  Select winner  ── or ──  refine (capped) → back to 1
9.  Inline gold-judge audit on the winner
10. ALWAYS write a Hallmark record + manifest to B2; status ∈
    {CERTIFIED, NEEDS_REVIEW, FAILED} reflects the outcome
```

Screening severity is differentiated, not uniform: **NSFW / prohibited content → hard gate** (and run early, before the VLM, since it's cheap and can reject outright); **brand-guide violation → configurable hard or soft criterion**; **possible logo / IP signal → warning, never an automatic legal rejection**.

### How Crucible wraps Genblaze's `AgentLoop`

`AgentLoop` evaluates *one output* per iteration, but a Crucible iteration produces a *bundle* of N candidates and runs a tournament. The mapping: **one AgentLoop iteration = one complete generation round.** The generation function returns a `CandidateBundle`; the evaluator runs the gates + tournament and returns a `RoundVerdict`, adapted into the `EvaluationResult` Genblaze expects. Genblaze owns the retry loop; Crucible owns fan-out, eligibility, ranking, and aggregated feedback.

```python
class CandidateBundle:        # the generator's logical output for one round
    iteration: int
    prompt: str
    candidates: list[Candidate]

class RoundVerdict:           # Crucible's evaluation of the round
    passed: bool              # selected candidate cleared ALL hard gates
    selected_attempt_id: str | None
    quality_score: float      # selected candidate's normalized weighted rubric score
    confidence: float         # reliability of the JUDGING process (≠ quality)
    feedback: str             # aggregated failure reasons → next prompt rewrite
    criterion_failures: list[str]

# Adapted into Genblaze's EvaluationResult — note the three are NOT interchangeable:
#   passed  = cleared all hard gates
#   score   = quality_score (how good the winner is)
#   (confidence is Crucible-internal; gates human escalation, not the loop)
EvaluationResult(
    passed=verdict.passed,
    score=verdict.quality_score,
    feedback=verdict.feedback,
)
```

A high-quality asset can still have *low* judging confidence (e.g. judges disagreed), so `score` and `confidence` are stored and used separately throughout.

### Live ensemble: conditional adjudicator

Running three judges on every candidate is wasteful. Crucible uses a **conditional adjudicator**:

- **Gemini 2.5 Flash** evaluates every candidate (the live judge).
- **Qwen2.5-VL** is invoked *only* when Gemini is low-confidence/inconsistent, **or** when the candidate was generated by a same-family model (e.g. Imagen → Google), satisfying the cross-family hygiene rule.
- **GPT-4o** audits the winner only (the gold judge).

### Judge confidence (computed, not self-reported)

`judge_confidence` is **derived from observable agreement signals**, never the model's own stated confidence (self-reported confidence is unreliable and prone to overconfidence/distribution collapse). Because the ensemble term only exists when Qwen was invoked, the weights **renormalize to sum to 1** based on which signals are present:

```
# If Qwen invoked (ensemble_agreement available):
confidence = 0.35 × order_symmetry        # forward vs reversed pairwise agree
           + 0.30 × ensemble_agreement    # Gemini vs Qwen agreement
           + 0.20 × criterion_consistency # rubric questions answered consistently
           + 0.15 × ranking_margin        # winner vs runner-up separation

# If Qwen NOT invoked: drop ensemble_agreement, renormalize the
# remaining weights (0.35 / 0.20 / 0.15 → 0.50 / 0.286 / 0.214)
```

`ranking_margin` (MVP) = `winner_pairwise_win_rate − runner_up_pairwise_win_rate`, normalized to [0, 1]. (A tournament doesn't yield a margin automatically; alternatives are Copeland score or Bradley–Terry probability — win-rate difference is sufficient for v1.)

**Breaking the Qwen-trigger circularity.** Qwen's invocation depends on confidence, but final confidence includes Qwen's agreement signal — circular. So Crucible computes a **`pre_adjudication_confidence`** *without* the ensemble term (order symmetry + criterion consistency + ranking margin, renormalized), uses it to decide whether to call Qwen, then computes the final confidence:

```
pre_adjudication_confidence = f(order_symmetry, criterion_consistency, ranking_margin)
if pre_adjudication_confidence < threshold  (or same-family candidate):
    invoke Qwen → final confidence includes ensemble_agreement
else:
    final confidence = pre_adjudication_confidence (no Qwen)
```

**Single eligible candidate** is a distinct path, not a renormalization: when only one candidate clears the hard gates, `order_symmetry` and `ranking_margin` *don't exist*. Crucible then skips the tournament, computes confidence from criterion consistency only, **invokes Qwen as an adjudicator**, and **requires live/gold agreement before certification** — safer than trusting one judge's criterion answers.

Weights are a starting point, to be calibrated against the human-labeled set (§10). Low confidence (below a calibrated threshold) routes to human escalation regardless of pass/fail.

### Certification decision policy

The gold judge must *change outcomes*, or it's decorative. Decision matrix:

| Live | Gold | Outcome |
|---|---|---|
| pass | pass | **CERTIFIED** automatically |
| pass | fail | **NEEDS_REVIEW** — no full certificate issued |
| fail | — | rejection retained; candidate refined or run **FAILED** |
| low confidence (either) | | **human escalation** |

The inline gold audit runs on the winner (which already passed live), so the cells in play per asset are *pass/pass* and *pass/fail*. The *live-fail + gold-pass* case (a possible false negative) is surfaced only through **offline sampling** of rejected candidates and feeds evaluator analysis, not a per-asset inline path.

**A Hallmark is always written**, even on disagreement or failure — only the `status` differs (`CERTIFIED` / `NEEDS_REVIEW` / `FAILED`). A disagreement preserves the full audit trail without issuing a certified claim.

### Run-state machine (drives SSE + stored metadata)

One vocabulary shared by backend, SSE stream, frontend progress UI, and stored run metadata. Every terminal path passes through `FINALIZING` (where the Hallmark record is written) — failures don't pass through `AUDITING`/certify:

```
CREATED → COMPILING_RUBRIC → GENERATING → CHECKING_DETERMINISTIC
        → CHECKING_OCR → CHECKING_SAFETY → JUDGING → RANKING
              ├─ no winner, attempts remain → REFINING → GENERATING
              ├─ no winner, exhausted       → FINALIZING → FAILED
              └─ winner                      → AUDITING
                    ├─ agreement              → FINALIZING → CERTIFIED
                    └─ disagree / low-conf    → FINALIZING → NEEDS_REVIEW
```

---

## 7. Data model on Backblaze B2

Use **`CONTENT_ADDRESSABLE`** keying for the candidate tree (dedupes identical candidates by SHA-256) and **`HIERARCHICAL`** for the run deliverables (grouped by run/date). Write structured eval data via **`ParquetSink`** for analytics. Apply **Object Lock** to certified Hallmarks for tamper-resistance — but record the *observed* lock metadata in a separate receipt (see below), never inside the hashed Hallmark.

**Object Lock config (MVP):**

```
- Mode:        governance   # bypassable with special perms — avoids undeletable dev files
                            # (consider compliance mode for production audit-trail use)
- Retention:   30 days
- Applied to:  certified hallmark.json only
- NOT locked:  failed candidates, winner asset, manifest (versioned but unlocked)
```

**Terminology.** A **Hallmark record** is written for *every* completed run. A **Certified Hallmark** has `status: CERTIFIED`; a **Review Hallmark** is `NEEDS_REVIEW`; a **Failure Hallmark** is `FAILED`. One schema, status distinguishes — "no certificate issued" means status ≠ CERTIFIED, not "no record written."

```
crucible/
  runs/{tenant}/{date}/{run_id}/
    brief.json                      # original brief + compiled rubric
    hallmark.json                   # the Hallmark record (immutable; Object Lock if CERTIFIED)
    hallmark-storage-receipt.json   # observed B2 lock metadata (written AFTER upload)
    pairwise-comparisons.json       # detailed tournament evidence
    round-{n}-manifest.json         # per-round Genblaze manifest (one per AgentLoop iteration)
    manifest.json                   # root/index manifest (points to round manifests)
    winner.{png|mp4|...}            # selected asset (manifest embedded)
    revocations/                    # append-only; never edits a locked Hallmark
      {revocation_id}.json
  candidates/                       # CONTENT_ADDRESSABLE (all attempts, all rounds)
    {sha[:2]}/{sha[2:4]}/{sha}.ext
  evals/                            # Parquet tables
    runs.parquet  candidates.parquet  scores.parquet
  audits/{date}/                    # cross-run analysis; references Hallmark hashes, never edits them
    judge-divergence-report.json
    diversity-collapse-report.json
```

**Avoiding a second circularity:** the B2 upload response (version_id, retain_until) *cannot* go inside `hallmark.json` — inserting it would change the document after it was hashed and uploaded, invalidating the hash and creating a new version. So `hallmark.json` records only the *requested* `storage_policy`; the *observed* result lives in `hallmark-storage-receipt.json`, which references the Hallmark's hash. The receipt may itself be locked (it just doesn't record its own lock metadata, ending the regress).

```jsonc
// hallmark-storage-receipt.json
{
  "schema_version": "1.0.0",
  "hallmark_sha256": "...",                 // the record this receipt attests to
  "bucket": "crucible-certificates",
  "object_key": "runs/.../hallmark.json",
  "version_id": "...",                      // from the B2 PUT response
  "object_lock": { "mode": "governance", "retain_until": "2026-08-14T18:42:00Z" },
  "observed_at": "..."
}

// revocations/{id}.json — REVOKED is append-only, never an edit to the locked Hallmark
{
  "type": "hallmark_revocation",
  "revoked_hallmark_sha256": "...",
  "reason": "...",
  "issued_at": "..."
}
```

**Hallmark certificate (extends, does not replace, the Genblaze manifest):**

```jsonc
{
  "schema_version": "1.0.0",
  "status": "CERTIFIED",              // run-level: CERTIFIED | NEEDS_REVIEW | FAILED
                                      // (REJECTED is a candidate-level status; REVOKED is a separate append-only record)
  "issued_at": "2026-07-15T18:42:00Z",
  "issuer": { "name": "Crucible", "version": "0.1.0" },

  "run_id": "...",
  "manifest_uri": "b2://.../manifest.json",   // root/index manifest; per-round manifests live in each round below

  "rubric": {
    "criteria": [
      {
        "id": "required_text",
        "description": "The front label contains the exact phrase 24 HOURS COLD",
        "type": "ocr_exact_match",
        "weight": 1.0,
        "hard_gate": true,
        "expected": "24 HOURS COLD",
        "evaluator": "paddleocr",
        "normalization": { "case_sensitive": false, "collapse_whitespace": true }
      },
      {
        "id": "white_background",            // deterministic — runs before the VLM
        "description": "Background is uniformly white AFTER excluding the product foreground",
        "type": "pixel_background_check",
        "weight": 1.0,
        "hard_gate": true,
        "expected": {
          "target_color": "#FFFFFF",
          "color_tolerance": 8,
          "background_pixel_pass_rate": 0.98,   // of BACKGROUND pixels, not all pixels
          "mask_method": "foreground_segmentation",
          "require_white_image_edges": true
        },
        "evaluator": "deterministic"
      },
      {
        "id": "product_uncropped",           // visual reasoning — the VLM
        "description": "Product is fully on-frame, not cropped at any edge",
        "type": "vlm_boolean",
        "weight": 1.0,
        "hard_gate": true,
        "evaluator": "gemini-2.5-flash"
      }
    ]
  },

  "rounds": [
    {
      "iteration": 0,
      "refined_prompt_sha256": "...",
      "genblaze": { "run_id": "...", "parent_run_id": null,
                    "manifest_uri": "b2://.../round-0-manifest.json" },
      "candidates": [
        { "attempt_id": "attempt_001", "candidate_index": 0,
          "model": "flux-1.1-pro", "provider": "gmicloud",
          "asset_uri": "b2://...", "asset_sha256": "...",
          "eligible": false, "failed_hard_gates": ["product_uncropped"],
          "criterion_results": [],
          "provider_request_id": "...", "seed": 12345,
          "generation_parameters": {}, "model_revision": "...", "response_timestamp": "..." },
        { "attempt_id": "attempt_002", "candidate_index": 1,
          "model": "sdxl", "provider": "replicate",
          "asset_uri": "b2://...", "asset_sha256": "...",
          "eligible": true, "failed_hard_gates": [],
          "criterion_results": [],
          "provider_request_id": "...", "seed": 33333,
          "generation_parameters": {}, "model_revision": "...", "response_timestamp": "..." }
      ]
    }
    // ... iteration 1: genblaze.parent_run_id links to round 0; its own candidate bundle ...
  ],

  "ranking": {
    "method": "bidirectional_pairwise_tournament",
    "eligible_attempt_ids": ["attempt_005", "attempt_006"],
    "winner_attempt_id": "attempt_006",
    "comparison_count": 2,
    "comparisons_uri": "b2://.../pairwise-comparisons.json"  // order, fwd/rev decisions, symmetry, reasoning
  },

  "winner": {
    "attempt_id": "attempt_006",        // unambiguous — iteration alone is not, a round holds many
    "iteration": 1,                      // asset hash resolved via attempt_id → integrity.asset_sha256 is canonical
    "rank_method": "pairwise",
    "judge_confidence": 0.91
  },

  "judge":      { "role": "live", "model": "gemini-2.5-flash", "family": "google",
                  "version": "...", "qwen_invoked": true },
  "gold_audit": { "role": "gold", "model": "gpt-4o", "family": "openai", "agreement": true },
  "within_run_diversity_index": 0.78,   // computed from THIS run's candidates; cross-run collapse lives in audits/

  "ip_risk_screening": {
    "status": "warning",
    "signals": ["possible third-party logo"],
    "legal_determination": false
  },

  "llm_calls": [
    { "purpose": "rubric_compile", "model": "gemini-2.5-flash", "version": "...",
      "input_prompt_sha256": "...", "output_sha256": "...",
      "tokens": { "in": 612, "out": 240 }, "cost_usd": 0.0021,
      "timestamp": "...", "parent_iteration": null },
    { "purpose": "prompt_rewrite", "model": "gpt-4o", "version": "...",
      "input_prompt_sha256": "...", "output_sha256": "...",
      "tokens": { "in": 880, "out": 130 }, "cost_usd": 0.0044,
      "timestamp": "...", "parent_iteration": 0 }
  ],

  "storage_policy": {                     // REQUESTED intent only; observed result is in the receipt
    "provider": "backblaze_b2",
    "object_lock_requested": true,
    "requested_mode": "governance",
    "requested_retention_days": 30
  },

  "integrity": {
    "canonicalization": "RFC8785",
    "hashed_fields_exclude": ["integrity.hallmark_sha256", "integrity.cryptographic_signature"],
    "asset_sha256": "...",                  // canonical asset hash lives ONLY here
    "hallmark_sha256": "...",
    "cryptographic_signature": null,        // stretch: { "algorithm": "Ed25519", "public_key_id": "...", "signature": "..." }
    "c2pa": {                               // stretch: null until actually embedded
      "status": "not_embedded",             // → "embedded" after implementation
      "assertion": null,                    // → "ai.generated"
      "manifest_store_hash": null
    }
  }
}
```

> **Fields are conditional on outcome.** The sample shows a CERTIFIED run; `winner`, `ranking`, `gold_audit`, and `integrity.asset_sha256` are **nullable**. A FAILED run has no winner, so they are `null`, and `pairwise-comparisons.json` exists only when ≥2 candidates were ranked.
>
> | Outcome | winner | ranking | gold_audit | asset_sha256 |
> |---|---|---|---|---|
> | CERTIFIED | required | optional (null if 1 eligible) | required | required |
> | NEEDS_REVIEW | required | optional (null if 1 eligible) | required | required |
> | FAILED | null | null | null | null |
>
> **On rounds/candidates & lineage** — best-of-N means each round holds *multiple* candidates from possibly different providers, so `winner` references an `attempt_id` (an `iteration` number alone is ambiguous). Each candidate carries eligibility and which hard gates it failed. Because one AgentLoop iteration = one round = one Genblaze run, each round embeds its own `genblaze` block (`run_id`, `parent_run_id`, `manifest_uri`) so rounds stay independently traceable and chained via `parent_run_id`; the top-level `manifest_uri` is the root/index. The `ranking` block summarizes the tournament; verbose per-comparison evidence lives in a separate `pairwise-comparisons.json`.
>
> **On diversity (within-run vs cross-run)** — `within_run_diversity_index` is computed from this run's candidates and can be written before the Hallmark is sealed. Cross-run collapse can only be measured across many runs, and a locked Hallmark can't be updated after the fact — so that analysis lives in `audits/{date}/diversity-collapse-report.json` and `judge-divergence-report.json`, which *reference* Hallmark hashes without modifying the sealed records.
>
> **On the rubric** — each criterion is fully self-describing (id, description, type, weight, hard_gate, expected value, evaluator, normalization) so the certificate is independently interpretable without the original application database. Note `white_background` is a deterministic pixel check (runs before any VLM call); `product_uncropped` is the visual-reasoning half, kept separate.
>
> **On the hash (avoiding circularity)** — `hallmark_sha256` cannot be computed over a document that already contains it. Crucible canonicalizes the Hallmark with RFC 8785 (JSON Canonicalization Scheme) while excluding `integrity.hallmark_sha256`, hashes that, then writes the value back. Verification repeats the exclude-canonicalize-hash and compares. `asset_sha256` lives only inside `integrity`; everything else references it.
>
> **On storage (a second circularity)** — the B2 upload response can't go inside the hashed Hallmark, so `storage_policy` records only *requested* intent; the *observed* lock metadata (version_id, retain_until) lives in `hallmark-storage-receipt.json` (§ storage tree above).
>
> **On integrity guarantees** — these are deliberately *not* one Boolean: `asset_sha256`/`hallmark_sha256` are tamper-*evidence* (detect change), the Object Lock receipt is tamper-*resistance* in B2 (prevent change), `cryptographic_signature` is *authenticity* (prove who issued it), and `c2pa` is *disclosure* (machine-readable AI marking supporting Article 50). MVP ships hashes + Object Lock; signing and C2PA are stretch and stay `null`/`not_embedded` until implemented.
>
> **On signing & C2PA ordering (stretch)** — two ordering rules matter when these ship. (1) A signature can't be inside the bytes it signs, so `integrity.cryptographic_signature` is excluded from canonicalization (already in `hashed_fields_exclude`) and the signature signs `hallmark_sha256`. (2) Embedding a C2PA manifest changes the asset bytes and thus its SHA-256, so the sequence is fixed: **generate winner → embed C2PA → compute final `asset_sha256` → build Hallmark → compute `hallmark_sha256` → optionally sign → upload & lock.** Never compute `asset_sha256` before C2PA embedding.
>
> **On `llm_calls` and replay** — rubric compilation and prompt rewriting are `chat()` calls, which Genblaze treats as outside the Pipeline, so its manifest will not record them; the Hallmark logs them itself. Candidates also capture `provider_request_id`, `seed`, `generation_parameters`, and `model_revision` when the provider exposes them. This gives **complete auditability and best-effort replay** — not guaranteed regeneration, since hosted APIs are nondeterministic and model revisions can change or disappear.

---

## 8. The Hallmark cert & C2PA relationship

- **Genblaze manifest** = *how it was made* (provider, model, prompt, params, SHA-256).
- **Hallmark** = *how it was verified* (rubric, full eval trajectory, judge identity/version, gold-judge audit, diversity index).
- **C2PA AI assertion** = *machine-readable disclosure* that **supports** EU AI Act Article 50 compliance (Crucible provides the disclosure marking; it does not by itself constitute a complete legal compliance program).

**Honest scoping (state this in the demo):** C2PA and the Hallmark both record that a *claim was made*, not that the content is *true*. C2PA credentials also don't survive CDN/metadata stripping without Durable Content Credentials, and the certificate-authority Trust List is still maturing. Crucible's contribution is the **quality/safety claim** layered on provenance, with Object Lock for tamper-evidence in trusted storage — not a truth oracle.

---

## 9. Vertical (v1): e-commerce product shots

Chosen because the criteria are near-objective and judge-reliable: white/transparent background, product centered and uncropped, correct aspect ratio, no garbled text, no anatomical/structural artifacts, brand-consistent. High volume, real pain, clean demo. **Bilingual/border-SMB extension** (bilingual product listings for border retailers) rides on top in a later phase. Marketing "creative quality" is deferred — too subjective for a reliable judge in v1.

---

## 10. Validation plan

**Goal:** prove the judge is trustworthy and the system beats baselines — the credibility of the entire project.

- **Ground-truth set:** 200–300 brief→image pairs in the e-comm vertical, human-labeled pass/fail per criterion. Refresh as generators change (benchmark-drift defense).
- **Anchor harnesses:** GenEval (553 compositional prompts), T2I-CompBench (attribute binding), DPG-Bench (dense prompts), TIFA (VQA faithfulness) for objective criteria.
- **Primary metric:** judge–human agreement (Cohen's κ; target κ ≥ 0.6 to gate unsupervised).
- **Secondary metrics:** (a) accepted-asset pass-rate vs. baselines; (b) human-review time saved; (c) cost per accepted asset.
- **Baselines:** single-shot generation; naive best-of-N with human pick; human-only review.
- **Reward-hacking measurement (the research result):** track live-judge vs. gold-judge agreement and the diversity index as N and iteration cap increase — show whether/when the proxy-true gap opens. This is the headline finding.

---

## 11. Economics

| Item | Cost |
|---|---|
| Standard image gen | $0.02–0.06 (Imagen 4 Fast $0.02, GPT Image 1.5 $0.04, Ideogram $0.03) |
| Aggregator gen (FAL/Replicate) | $0.002–0.008 |
| VLM judge call | ≈ one image or less |
| Best-of-4 + judge, 1 round | ~$0.20–0.25 |
| Capped loop (≤3 rounds) worst case | < $0.70 / accepted asset |
| Human designer (context) | $60k–120k / yr |

Batch APIs cut generation cost ~50%. **Framing: Crucible automates the 3–10 iterations workflows already do — it's not new overhead, and it's below human review cost-per-asset at volume.**

---

## 12. Phased build plan (to Aug 3)

- **Phase 0 — Spine (week 1).** Genblaze quickstart → B2 storage → one provider → manifest verified. Stand up the repo, env, B2 bucket + app key.
- **Phase 1 — Judge MVP (week 1–2).** Rubric compiler + cross-family VLM judge returning `EvaluationResult`; wire into `AgentLoop`. OCR check. Single provider, single criterion set (e-comm).
- **Phase 2 — Fan-out + routing (week 2).** Parallel best-of-N across two-provider stack; pairwise ranking selection; routing config via `ModelRegistry`.
- **Phase 3 — Certification + storage (week 2–3).** Hallmark cert data model; content-addressable attempt tree + hierarchical deliverables; Object Lock; Parquet eval tables; optional C2PA assertion.
- **Phase 4 — Validation + reward-hacking audit (week 3).** Label the 200–300 set; compute κ and baselines; gold-judge + diversity monitor; produce the headline numbers.
- **Phase 5 — UI + demo + submission (week 3–4).** Brief input, gauntlet dashboard (attempts/scores/rejections), 3-min demo video, README with setup, GitHub access for judges, Devpost write-up listing providers/models and B2+Genblaze usage.

---

## 13. Risks & mitigations

| Risk | Mitigation |
|---|---|
| Judge unreliable on subjective criteria | v1 stays in objective-criteria vertical; subjective items soft-weighted; human escalation on low confidence |
| Reward hacking | Capped optimization pressure (BoN, not gradient); cross-family gold-judge audit; diversity monitor |
| Position/self-preference bias | Order randomization + averaging; cross-family judge |
| Benchmark/judge drift | Periodic re-anchor to fresh human labels; judge versioned in the cert |
| Cost blowup | Batch APIs; aggregator tier for drafts; cap N and iterations |
| "Just our SDK with a UI" critique | Lead with the evaluator + routing + cert as the contribution; consider an issue/PR to genblaze with the evaluator pattern |
| Video latency in demo | Demo on images; mention video as a Genblaze-native extension |

---

## 14. Documentation & reference links

**Genblaze / Backblaze (primary build docs)**
- Genblaze Developer Guide — https://www.backblaze.com/docs/en/cloud-storage-genblaze-developer-guide
- Genblaze GitHub repo — https://github.com/backblaze-labs/genblaze
- Genblaze feature docs (pipeline, agents, sinks, policy, observability) — https://github.com/backblaze-labs/genblaze/tree/main/docs/features
- Genblaze trust modes — https://github.com/backblaze-labs/genblaze/blob/main/docs/features/trust-modes.md
- Genblaze model registry — https://github.com/backblaze-labs/genblaze/blob/main/docs/features/model-registry.md
- Genblaze new-provider guide — https://github.com/backblaze-labs/genblaze/blob/main/docs/guides/new-provider.md
- Backblaze B2 docs home — https://www.backblaze.com/docs
- B2 create & manage buckets — https://www.backblaze.com/docs/cloud-storage-create-and-manage-buckets
- B2 app keys — https://www.backblaze.com/docs/cloud-storage-create-and-manage-app-keys
- B2 Object Lock — https://www.backblaze.com/docs/cloud-storage-enable-object-lock-or-a-legal-hold-on-an-existing-bucket
- GMI Cloud (hackathon credits) — https://www.gmicloud.ai/
- Hackathon page — https://backblaze-generative-media.devpost.com/

**Evaluation benchmarks (judge validation harness)**
- GenEval — https://arxiv.org/abs/2310.11513
- GenEval 2 (benchmark drift) — https://arxiv.org/abs/2512.16853
- T2I-CompBench / ++ — https://arxiv.org/abs/2307.06350
- DPG-Bench — https://arxiv.org/abs/2403.05135
- TIFA — https://arxiv.org/abs/2303.11897

**VLM-as-judge reliability & bias**
- VLM Judges Can Rank but Cannot Score — https://arxiv.org/abs/2604.25235
- MLLM-as-a-Judge — https://arxiv.org/abs/2402.04788
- Judging the Judges: Position Bias in LLM-as-a-Judge — https://arxiv.org/abs/2406.07791

**Iterative refinement vs. best-of-N**
- Iterative Refinement Improves Compositional Image Generation — https://arxiv.org/abs/2601.15286
- Test-time Prompt Refinement for T2I — https://arxiv.org/abs/2507.22076
- RePrompt (RL reprompting) — https://arxiv.org/abs/2505.17540

**Reward hacking / overoptimization (the research angle)**
- Scaling Laws for Reward Model Overoptimization (Gao et al.) — https://arxiv.org/abs/2210.10760
- Understanding Reward Hacking in T2I RL — https://arxiv.org/abs/2601.03468
- MIRA (mitigating reward hacking in T2I) — https://arxiv.org/abs/2510.01549
- Inference-Time Reward Hacking in LLMs — https://arxiv.org/abs/2506.19248

**Provenance / regulation (the "why now")**
- C2PA specification — https://c2pa.org/specifications/
- EU AI Act Article 50 — https://artificialintelligenceact.eu/article/50/
- California SB 942 — https://leginfo.legislature.ca.gov/faces/billTextClient.xhtml?bill_id=202320240SB942

**Provider pricing (economics)**
- Google Gemini/Imagen pricing — https://ai.google.dev/gemini-api/docs/pricing
- OpenAI API pricing — https://openai.com/api/pricing/

**Tech stack**
- Genblaze spec (TS types, npm) — https://www.npmjs.com/package/@genblaze/spec
- GMICloud — https://www.gmicloud.ai/
- Replicate API — https://replicate.com/docs
- FastAPI — https://fastapi.tiangolo.com/
- Next.js — https://nextjs.org/docs
- Vercel — https://vercel.com/docs
- Modal (serverless Python) — https://modal.com/docs
- PaddleOCR — https://github.com/PaddlePaddle/PaddleOCR
- DuckDB — https://duckdb.org/docs/
- Supabase — https://supabase.com/docs
- Gemini API (live judge) — https://ai.google.dev/gemini-api/docs
- OpenAI models (gold judge) — https://platform.openai.com/docs/models
- Qwen2.5-VL — https://github.com/QwenLM/Qwen2.5-VL

---

## 15. Success criteria — mapped to judging rubric

- **Use of Genblaze:** exercises `AgentLoop`, `CallableEvaluator`/`EvaluationResult`, `chat()`, parallel/`batch_run`, `fallback_models`, `Manifest`, `parent_run_id`, `ModelRegistry`, `EmbedPolicy`. The evaluator fills the SDK's one explicit blank.
- **B2 Storage & Data Orchestration:** manifests + Hallmark certs + Object Lock + content-addressable attempt tree + Parquet eval tables.
- **Production Readiness:** retry policies, streaming progress, OpenTelemetry, human escalation on low judge confidence.
- **Real-World Utility:** objective-criteria e-comm vertical with a measured κ and human-review-time savings, plus the Aug 2 EU AI Act compliance hook.

**Stretch (fellowship-grade):** the reward-hacking measurement — live-judge vs. gold-judge divergence as a function of optimization pressure — as a short writeup. Novel for media, defensible as research, and the strongest narrative for AI-safety fellowship applications.
