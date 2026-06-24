# Crucible Development Plan

This plan turns the Crucible PRD into an implementation roadmap that preserves the full product vision while adding the live deployment requirements for the Backblaze Generative Media Hackathon.

The key planning change is that the live app is not saved for the end. A minimal deployed app is built early, then upgraded phase by phase as the judge, fan-out, Hallmark certification, validation, and demo polish land.

## Submission Constraints

The hackathon submission must include:

- A working live application URL that judges can access and test.
- A GitHub repository URL with source code, assets, and setup instructions.
- A public demo video under 3 minutes on YouTube, Vimeo, or Youku.
- A text description explaining features, B2 usage, Genblaze usage, and AI providers/models used.
- Free and unrestricted judge access through the judging period.
- English submission materials or English testing instructions.

Important dates:

- Submission deadline: August 3, 2026, 5:00pm EDT.
- Judging period: August 5-11, 2026.

Primary deployment target:

- Frontend: Next.js on Vercel.
- Backend: FastAPI on Modal.
- Storage: Backblaze B2.
- Generation orchestration: Genblaze.
- v1 auth: no auth, with cost guardrails instead.

## Product Outcome

Crucible turns a creative brief into a certified AI media asset.

The final hackathon build should:

1. Accept an e-commerce product-shot brief.
2. Compile the brief into a checkable rubric.
3. Generate candidate assets through Genblaze.
4. Store assets, manifests, evaluation artifacts, and Hallmark records in B2.
5. Run deterministic checks before expensive model checks.
6. Run OCR for text legibility rather than relying on a VLM.
7. Run safety, brand, and IP-risk screening.
8. Judge eligible candidates with a cross-family VLM strategy.
9. Rank candidates pairwise instead of trusting absolute VLM scores.
10. Refine failed attempts with memory, capped iterations, and optional rerouting.
11. Write a Hallmark record for every terminal run.
12. Object-lock certified Hallmarks and store observed lock metadata separately.
13. Display the full gauntlet trajectory in a live dashboard.
14. Provide validation evidence that the judge tracks human labels and detects reward-hacking pressure.

## Architecture Target

The final system should use this flow:

```text
Brief
  -> Rubric compiler
  -> Generation fan-out through Genblaze
  -> Candidate asset storage in B2
  -> Deterministic checks
  -> OCR checks
  -> Safety, brand, and IP-risk screening
  -> VLM criterion checks
  -> Hard-gate filtering
  -> Pairwise ranking
  -> Winner selection or refinement
  -> Gold-judge audit
  -> Hallmark record
  -> B2 storage receipt and optional Object Lock
  -> Live dashboard display
```

Core packages and apps:

- `packages/crucible-core`: generation, rubric, checks, judge, refinement, certification, storage, telemetry, validation.
- `apps/api`: FastAPI run orchestration, SSE or polling endpoints, asset/Hallmark access.
- `apps/web`: Next.js dashboard for brief input, run progress, candidates, verdicts, and Hallmark viewing.
- `configs`: model registry, routing, judge policy, storage policy, rubric definitions.
- `scripts`: local spine commands, verification commands, export tools, validation helpers.

## Phase 0 - Repository And Live Storage Spine

Goal: prove one local command can generate or fake-generate one asset, store it, write a manifest, and verify the manifest hash.

Current status:

- Python project scaffold exists.
- Dry-run generator exists.
- Local B2-shaped storage exists.
- `.env` loader exists.
- Manifest verification exists.
- Tests pass locally: 5 passed, 1 skipped.

Remaining implementation:

- Confirm live Genblaze imports and API surface from installed packages.
- Update the live adapter to the actual Genblaze SDK entry points.
- Add env alias support for common Genblaze names:
  - `GMICLOUD_API_KEY` and `GMI_API_KEY`
  - `B2_APPLICATION_KEY_ID` and `B2_KEY_ID`
  - `B2_APPLICATION_KEY` and `B2_APP_KEY`
- Run a real GMICloud generation.
- Upload the asset and manifest to B2.
- Verify the live manifest hash against B2 asset bytes.
- Confirm no secrets appear in logs, manifests, terminal output, or README examples.

Acceptance criteria:

- `python scripts/phase0_generate.py --brief examples/ecommerce-product-shot/brief.json` succeeds with real Genblaze and B2.
- `python scripts/verify_manifest.py --run-id <run_id>` verifies the live B2 asset hash.
- B2 contains `runs/local/{run_id}/asset.png` and `runs/local/{run_id}/manifest.json`.
- README setup works from a fresh clone.

Tests:

- Unit tests for config, hash helper, object key builder, `.env` loader, and local manifest round trip.
- Opt-in live test gated by `CRUCIBLE_RUN_LIVE_PROVIDER_TESTS=true`.

## Phase 0.5 - Minimal Live App Shell

Goal: remove deployment risk early by turning the Phase 0 spine into a publicly accessible app before building the deep evaluator.

Backend implementation:

- Add `apps/api` with FastAPI.
- Add `POST /runs`:
  - Accepts a brief payload.
  - Creates a `run_id`.
  - Runs the existing Phase 0 generation path.
  - Stores asset and manifest in B2.
  - Returns run metadata.
- Add `GET /runs/{run_id}`:
  - Returns current status, asset URI, manifest URI, asset hash, and verification status.
- Add `GET /health`:
  - Confirms service health without exposing secrets.
- Start with synchronous request handling for the minimal demo.
- Add background jobs or Modal functions once generation latency requires it.

Frontend implementation:

- Add `apps/web` with Next.js, TypeScript, and Tailwind.
- First screen is the working app, not a landing page.
- Include:
  - Brief input textarea.
  - Generate button.
  - Run status.
  - Generated image preview.
  - Manifest URI.
  - Asset SHA-256.
  - Verification status.
  - Provider/model used.
- Do not require authentication for v1 judging.
- Add simple cost guardrails:
  - Limit prompt length.
  - Limit one candidate per run in this phase.
  - Add backend timeout.
  - Optionally include a small set of demo prompts.

Deployment implementation:

- Add Modal deployment config for FastAPI.
- Add Vercel deployment config for Next.js.
- Add production env var checklist.
- Store all provider and B2 secrets only in Modal secrets, not Vercel.
- Vercel receives only `NEXT_PUBLIC_API_BASE_URL`.

Acceptance criteria:

- Public frontend URL loads.
- A judge can submit a brief without signing in.
- The app generates an asset through Genblaze and stores it in B2.
- The app displays image, manifest URI, hash, and verification status.
- The app remains usable without local developer tools.

Tests:

- Backend route tests with fake generator and fake storage.
- Frontend smoke test for brief form and result rendering.
- Manual deployed test from a clean browser session.

## Phase 1 - Domain Models, Rubric, And Judge MVP

Goal: add the first real Crucible evaluator path while staying single-provider and simple enough to debug.

Domain model implementation:

- Move the Pydantic models from `PYDANTIC_DOMAIN_MODELS.md` into `packages/crucible-core/src/crucible/domain`.
- Split once useful into:
  - `base.py`
  - `brief.py`
  - `rubric.py`
  - `candidate.py`
  - `ranking.py`
  - `judge.py`
  - `hallmark.py`
  - `storage.py`
- Preserve invariants:
  - One run has one or more rounds.
  - One round has multiple attempts.
  - Winner references `attempt_id`.
  - `quality_score` and `judge_confidence` are separate.
  - Failed runs may have no winner, ranking, gold audit, or asset hash.

Rubric implementation:

- Add `configs/rubrics/ecommerce-product-shot.yaml`.
- Start with a static e-commerce rubric before LLM compilation:
  - Correct aspect ratio.
  - Minimum resolution.
  - Valid image file.
  - White or transparent background.
  - Product centered.
  - Product uncropped.
  - Required text legible when present.
  - No obvious structural artifacts.
  - Brand consistency as a soft criterion.
- Add a rubric compiler interface so LLM-based compilation can replace or augment the static rubric.
- Log future rubric compiler `chat()` calls in Hallmark `llm_calls`, because Genblaze manifests will not capture them automatically.

Deterministic checks:

- File integrity.
- MIME/type validation.
- Image decode validation.
- Width and height.
- Aspect ratio.
- Basic white-background edge check.
- Transparent-background check where applicable.

Judge MVP:

- Add a live judge abstraction that returns `RoundVerdict`.
- Add adapter from `RoundVerdict` to Genblaze `EvaluationResult`.
- Use Gemini 2.5 Flash as the configured live VLM judge.
- Keep this phase to one candidate and one round unless the Genblaze AgentLoop wiring requires a retry.
- Record judge model, family, version when exposed, and feedback.

Live app upgrade:

- Show the compiled/static rubric.
- Show deterministic check results.
- Show judge verdict.
- Show whether the run is `CERTIFIED`, `NEEDS_REVIEW`, or `FAILED` in preliminary form.

Acceptance criteria:

- A generated candidate receives check results and a judge verdict.
- Backend exposes run state through the API.
- Frontend displays pass/fail reasons.
- `EvaluationResult` integration is isolated at the Genblaze boundary.

Tests:

- Pydantic validation tests.
- Deterministic check tests using fixture images.
- Fake judge tests.
- API tests with fake generator, fake storage, and fake judge.

## Phase 2 - OCR, Safety, Brand, And IP-Risk Gates

Goal: complete the pre-ranking eligibility layer so expensive ranking only sees eligible candidates.

OCR implementation:

- Add PaddleOCR integration.
- Compare extracted text against `required_text`.
- Support normalized exact matching:
  - Case-insensitive by default.
  - Collapse whitespace by default.
  - Preserve strict mode option for later.
- Keep OCR independent from VLM judging.
- Add EN first, ES once bilingual examples are added.

Safety implementation:

- Add cheap safety screening before VLM judging.
- NSFW/prohibited content is a hard gate.
- Store safety signals in candidate evidence.
- Avoid exposing unsafe generated images in the public UI if the safety gate blocks them.

Brand implementation:

- Support brand-guideline criteria from the brief.
- Allow brand checks to be configured as hard or soft.
- Store brand feedback as criterion results.

IP-risk implementation:

- Add a warning-only IP-risk screening pass.
- Possible third-party logo, character, or trademark-like signals never become legal determinations.
- Store `legal_determination: false` in records.

Live app upgrade:

- Add criterion-level results table.
- Add warning badges for IP-risk signals.
- Add clear separation between hard failures, soft warnings, and judge feedback.

Acceptance criteria:

- OCR catches missing or garbled required text in fixtures.
- NSFW/prohibited content can fail a run before VLM ranking.
- IP-risk warnings do not automatically reject an otherwise eligible candidate.
- UI makes hard-gate vs warning status obvious.

Tests:

- OCR normalization tests.
- Safety hard-gate tests with mocked classifier outputs.
- IP-risk warning-only tests.
- API serialization tests for criterion evidence.

## Phase 3 - Fan-Out, Routing, And Pairwise Ranking

Goal: move from one candidate to Crucible's core best-of-N gauntlet.

Generation fan-out:

- Use Genblaze parallel execution or `batch_run` for N candidates.
- Default N: 4.
- Maximum N: 8.
- Core providers:
  - GMICloud.
  - Replicate.
- Store every candidate attempt, including failed attempts.
- Each candidate gets:
  - `attempt_id`
  - provider
  - model
  - asset URI
  - asset SHA-256
  - provider request ID when exposed
  - generation parameters
  - model revision when exposed

Routing policy:

- Add `configs/routing.yaml`.
- Add config-driven model registry use.
- Do not build a learned router for v1.
- Use quality, cost, latency, and criterion strength weights.
- Imagen 4 remains premium fallback only after quality misses, not normal fan-out.

Pairwise ranking:

- Rank only candidates that pass all hard gates.
- Use bidirectional pairwise tournament.
- Randomize candidate order.
- Evaluate forward and reverse orders where cost permits.
- Store order symmetry.
- Compute ranking margin as winner pairwise win rate minus runner-up win rate.
- Keep absolute VLM scores secondary to ranking.

Confidence:

- Compute `pre_adjudication_confidence` from:
  - order symmetry
  - criterion consistency
  - ranking margin
- Invoke Qwen2.5-VL only when:
  - pre-adjudication confidence is low
  - Gemini is inconsistent
  - the candidate was generated by a same-family model
- Compute final `judge_confidence` after optional Qwen agreement.
- Do not trust model self-reported confidence.

Live app upgrade:

- Add candidate grid.
- Add per-candidate gate status.
- Add winner highlight.
- Add pairwise ranking summary.
- Add confidence panel.

Acceptance criteria:

- One run can generate multiple candidates.
- Ineligible candidates are removed before ranking.
- Winner is selected by `attempt_id`.
- Ranking evidence is stored separately from the summary.
- UI shows every candidate and why it lost or failed.

Tests:

- Candidate bundle tests.
- Hard-gate filtering tests.
- Ranking winner eligibility tests.
- Confidence calculation tests.
- Fake multi-provider integration tests.

## Phase 4 - Refinement Loop And AgentLoop Integration

Goal: make Crucible retry intelligently when the first generation round does not clear the bar.

AgentLoop mapping:

- One Genblaze AgentLoop iteration equals one Crucible generation round.
- The generator returns a `CandidateBundle`.
- The evaluator runs checks, ranking, and aggregation.
- The evaluator returns `RoundVerdict`.
- The Genblaze boundary adapts `RoundVerdict` to `EvaluationResult`.

Refinement:

- On fail, rewrite the full prompt rather than appending notes.
- Include full attempt history and feedback memory.
- Optionally reroute model based on failure reason.
- Cap at 3 refinement iterations.
- Log each prompt rewrite in Hallmark `llm_calls`.

Routing on failure:

- Text failure can route toward a stronger text-rendering model.
- Photorealism or product-quality failure can trigger premium fallback.
- Safety failure does not retry blindly with the same prompt; it rewrites or stops depending on severity.
- Repeated low-confidence judging can route to human review / `NEEDS_REVIEW`.

Live app upgrade:

- Add gauntlet timeline:
  - Compiling rubric.
  - Generating.
  - Checking deterministic gates.
  - Checking OCR.
  - Checking safety.
  - Judging.
  - Ranking.
  - Refining.
  - Auditing.
  - Finalizing.
- Add round-by-round prompt and feedback hashes.
- Show why a retry happened.

Acceptance criteria:

- Failed round can trigger a refined second round.
- Refinement stops at configured cap.
- Every round has traceable candidates and manifests.
- UI shows the full retry trajectory.

Tests:

- Prompt memory tests.
- Refinement cap tests.
- Failure-reason routing tests.
- AgentLoop adapter tests with fake Genblaze objects.

## Phase 5 - Hallmark Certification And B2 Data Model

Goal: implement the durable certification layer that makes Crucible more than a generation UI.

Hallmark record:

- Always write a Hallmark record for every terminal run.
- Status values:
  - `CERTIFIED`
  - `NEEDS_REVIEW`
  - `FAILED`
- Candidate-level rejected status is not the same as run-level failed status.
- Revocation is append-only and separate.

Hallmark contents:

- Schema version.
- Run ID.
- Issuer name/version.
- Root Genblaze manifest URI.
- Rubric and all criteria.
- Rounds and candidates.
- Ranking summary.
- Winner when present.
- Judge identity and version.
- Gold audit when present.
- Within-run diversity index.
- IP-risk screening signals.
- LLM call hashes and costs.
- Storage policy requested.
- Integrity block.

Hashing:

- Use RFC 8785-style canonical JSON.
- Exclude `integrity.hallmark_sha256`.
- Exclude `integrity.cryptographic_signature`.
- Compute `hallmark_sha256`.
- Write `asset_sha256` only in `integrity`.
- Verification repeats exclude, canonicalize, hash, compare.

B2 layout:

```text
crucible/
  runs/{tenant}/{date}/{run_id}/
    brief.json
    hallmark.json
    hallmark-storage-receipt.json
    pairwise-comparisons.json
    round-{n}-manifest.json
    manifest.json
    winner.{png|mp4|...}
    revocations/
      {revocation_id}.json
  candidates/
    {sha[:2]}/{sha[2:4]}/{sha}.ext
  evals/
    runs.parquet
    candidates.parquet
    scores.parquet
  audits/{date}/
    judge-divergence-report.json
    diversity-collapse-report.json
```

Object Lock:

- MVP mode: governance.
- Retention: 30 days.
- Apply to certified `hallmark.json` only.
- Do not lock failed candidates, winner asset, or normal manifests by default.
- Store observed lock metadata in `hallmark-storage-receipt.json`, not inside the hashed Hallmark.

Parquet analytics:

- Write structured eval tables through Genblaze `ParquetSink` or a compatible local exporter.
- Include runs, candidates, criterion scores, pairwise comparisons, costs, latencies.

C2PA:

- Stretch for hackathon unless time permits.
- Keep `c2pa.status` as `not_embedded` until actually implemented.
- If implemented, sequence must be:
  - generate winner
  - embed C2PA
  - compute final `asset_sha256`
  - build Hallmark
  - compute `hallmark_sha256`
  - optionally sign
  - upload and lock

Live app upgrade:

- Add Hallmark viewer.
- Add manifest vs Hallmark explanation.
- Add verification status.
- Add B2 object links or copyable URIs.
- Add storage receipt display for certified Hallmarks.

Acceptance criteria:

- Hallmark is written for certified, needs-review, and failed runs.
- Failed run has no winner/gold audit/asset hash fields when not applicable.
- Certified Hallmark verifies by hash.
- Storage receipt is separate from the hashed Hallmark.
- UI can display the Hallmark without requiring database truth.

Tests:

- Canonicalization and hash tests.
- Outcome-dependent Hallmark validation tests.
- Storage receipt separation tests.
- Object key layout tests.
- Hallmark verifier tests.

## Phase 6 - Gold Audit, Validation, And Reward-Hacking Measurement

Goal: prove the judge is trustworthy enough to be credible.

Gold audit:

- Run GPT-4o as gold judge on the selected winner.
- Record agreement with live judge.
- Store disagreement as `NEEDS_REVIEW` when confidence is too low.
- Keep gold audit cross-family from the generator and live judge where possible.

Validation dataset:

- Build 200-300 e-commerce brief/image pairs.
- Human-label pass/fail per criterion.
- Include:
  - white background
  - transparent background
  - centered product
  - uncropped product
  - aspect ratio
  - required text
  - structural artifact
  - brand consistency
- Refresh labels as generator quality changes.

Metrics:

- Primary: judge-human agreement, Cohen's kappa target >= 0.6 before unsupervised claims.
- Secondary:
  - accepted-asset pass rate vs baselines
  - human-review time saved
  - cost per accepted asset
  - latency per accepted asset

Baselines:

- Single-shot generation.
- Naive best-of-N with human pick.
- Human-only review.

Reward-hacking measurement:

- Track live-judge vs gold-judge divergence.
- Track within-run diversity index.
- Plot divergence as N and iteration cap increase.
- Watch for diversity collapse as optimization pressure rises.
- Keep capped best-of-N and capped refinement as deliberate mitigation.

Benchmark harnesses:

- GenEval for compositional prompts.
- T2I-CompBench for attribute binding.
- DPG-Bench for dense prompts.
- TIFA-style objective visual questions.

Live app upgrade:

- Add a metrics/admin view if time permits.
- Otherwise include generated reports in repo and Devpost materials.
- Show one headline validation result in the demo app or README.

Acceptance criteria:

- Gold audit runs on winners.
- Validation script computes kappa.
- Baseline comparison report exists.
- Reward-hacking/diversity report exists or a smaller documented pilot exists.

Tests:

- Kappa calculation tests.
- Diversity metric tests.
- Gold-audit serialization tests.
- Report generation tests.

## Phase 7 - Production Hardening And Observability

Goal: make the live app stable enough for judges and credible enough for the submission.

Run-state machine:

Use one shared vocabulary across backend, frontend, SSE/polling, and stored metadata:

```text
CREATED
COMPILING_RUBRIC
GENERATING
CHECKING_DETERMINISTIC
CHECKING_OCR
CHECKING_SAFETY
JUDGING
RANKING
REFINING
AUDITING
FINALIZING
CERTIFIED
NEEDS_REVIEW
FAILED
```

API hardening:

- Move long jobs to Modal background functions.
- Add polling first, SSE second if needed.
- Add request timeout.
- Add run cancellation if practical.
- Add clear error envelopes.
- Redact secrets in all error messages.
- Store run state so page refresh does not lose the result.

Cost controls:

- Maximum candidates per round: 8.
- Default candidates per round: 4.
- Maximum refinement iterations: 3.
- Public demo mode may use a stricter cap.
- Optional daily run cap.
- Optional prompt presets.
- Provider-level spend caps where supported.

Observability:

- Add structured logs with run ID, round, attempt ID, provider, model, cost, latency.
- Add OpenTelemetry hooks.
- Add local `LoggingTracer`.
- Optional Honeycomb or Jaeger export.
- Never log API keys, raw secrets, or unredacted sensitive prompts.

Security:

- No provider secrets in frontend.
- No B2 write credentials in frontend.
- Backend owns all provider and B2 calls.
- Public app uses cost controls instead of auth.
- If auth becomes necessary, include a judge test account and instructions.

Deployment:

- Modal backend:
  - stores provider keys and B2 keys as secrets
  - includes OCR dependencies
  - exposes public API endpoint
- Vercel frontend:
  - only public API base URL
  - no provider keys
  - no B2 keys
- B2:
  - bucket created
  - Object Lock enabled if required for certified Hallmarks
  - scoped app key

Acceptance criteria:

- Public frontend and backend stay online.
- Fresh browser can run the demo.
- Logs are useful but secret-free.
- Failure states are visible and understandable.
- App remains free and unrestricted for judges through August 11, 2026.

Tests:

- API error tests.
- Serialization tests for all run states.
- Frontend render tests for each terminal status.
- Deployed smoke test checklist.

## Phase 8 - Submission Package

Goal: deliver the hackathon artifacts with no ambiguity for judges.

README:

- Project summary.
- Live app URL.
- Demo video URL.
- Setup instructions.
- Environment variable guide.
- Local dry-run instructions.
- Live B2/Genblaze instructions.
- Architecture overview.
- Providers and models used.
- B2 storage explanation.
- Genblaze SDK usage explanation.
- Known limitations.
- Honest compliance scope.

GitHub repository:

- Public preferred for simpler judging.
- Private acceptable only if sponsor testing account access is granted.
- Ensure `.env` is ignored.
- Ensure no generated secret-bearing artifacts are committed.
- Include small fixtures only.

Demo video:

- Under 3 minutes.
- Publicly visible on YouTube, Vimeo, or Youku.
- Show the live app working.
- Show brief submission.
- Show candidates and gauntlet progression.
- Show winner or needs-review verdict.
- Show Hallmark/manifest/B2 evidence.
- State providers/models used.
- Avoid copyrighted music and third-party trademarks.

Devpost text:

- Explain features:
  - generate
  - judge
  - retry/refine
  - certify
  - store provenance
- Explain B2 usage:
  - assets
  - manifests
  - Hallmarks
  - Object Lock
  - Parquet/eval artifacts
- Explain Genblaze usage:
  - Pipeline
  - AgentLoop
  - EvaluationResult
  - Manifest
  - ModelRegistry
  - provider adapters
- List providers/models:
  - GMICloud models used
  - Replicate models used
  - Gemini 2.5 Flash
  - GPT-4o
  - Qwen2.5-VL
  - Imagen 4 if used
- Include honest scope:
  - Hallmark records a quality/safety claim, not truth.
  - IP-risk is warning-only, not legal determination.
  - C2PA is stretch unless actually embedded.

Final acceptance checklist:

- Live app URL works.
- Repo URL works.
- Demo video URL works.
- README setup works.
- Judges can test without payment.
- App will remain available through judging.
- No secrets are committed.
- Submission materials are in English.

## Feature Traceability Matrix

| PRD feature | Planned phase |
|---|---|
| Genblaze quickstart and one-provider generation | Phase 0 |
| B2 storage and manifest verification | Phase 0 |
| Live working application URL | Phase 0.5 |
| FastAPI backend | Phase 0.5 |
| Next.js frontend | Phase 0.5 |
| Pydantic domain models | Phase 1 |
| E-commerce product-shot vertical | Phase 1 |
| Rubric compiler/static rubric | Phase 1 |
| Deterministic checks | Phase 1 |
| Genblaze `EvaluationResult` adapter | Phase 1 |
| OCR text legibility check | Phase 2 |
| Safety screening | Phase 2 |
| Brand screening | Phase 2 |
| IP-risk warning signals | Phase 2 |
| Multi-provider fan-out | Phase 3 |
| GMICloud provider | Phase 0 and Phase 3 |
| Replicate provider | Phase 3 |
| Imagen premium fallback | Phase 3 or Phase 4 |
| Config-driven routing | Phase 3 |
| Pairwise/tournament ranking | Phase 3 |
| Order randomization and symmetry | Phase 3 |
| Judge confidence calculation | Phase 3 |
| Qwen conditional adjudication | Phase 3 |
| AgentLoop round mapping | Phase 4 |
| Iterative prompt refinement | Phase 4 |
| Full attempt memory | Phase 4 |
| Capped optimization pressure | Phase 4 |
| Hallmark schema | Phase 5 |
| Hallmark hashing and verification | Phase 5 |
| Object Lock for certified Hallmarks | Phase 5 |
| Storage receipt separation | Phase 5 |
| Content-addressable candidate tree | Phase 5 |
| Parquet eval tables | Phase 5 |
| C2PA assertion | Stretch in Phase 5 |
| GPT-4o gold audit | Phase 6 |
| Human-label validation set | Phase 6 |
| Cohen's kappa | Phase 6 |
| Baseline comparison | Phase 6 |
| Reward-hacking/diversity monitor | Phase 6 |
| OpenTelemetry/logging | Phase 7 |
| SSE or polling run progress | Phase 7 |
| Cost controls | Phase 7 |
| Demo video and Devpost materials | Phase 8 |

## Recommended Build Order From Today

1. Finish live Phase 0 with real Genblaze and B2.
2. Create the GitHub repo and push the current Phase 0 scaffold.
3. Add Phase 0.5 live app shell and deploy it.
4. Add domain models and deterministic e-commerce rubric.
5. Add one live judge path.
6. Add OCR, safety, brand, and IP-risk checks.
7. Add fan-out and pairwise ranking.
8. Add refinement and AgentLoop integration.
9. Add Hallmark and B2 certification storage.
10. Add validation and gold audit.
11. Harden the live app.
12. Produce README, demo video, and Devpost text.

The guiding principle: keep the whole PRD, but keep a live URL working after Phase 0.5 so every later feature is an upgrade to a real application rather than a last-minute deployment scramble.
