# Crucible Repository Structure

This artifact translates the PRD into a practical monorepo layout for building Crucible: a Genblaze-powered generate, judge, refine, and certify pipeline for AI media.

## Recommended Layout

```text
crucible/
  README.md
  pyproject.toml
  package.json
  pnpm-workspace.yaml
  .env.example
  .gitignore

  docs/
    prd.md
    architecture.md
    repository-structure.md
    demo-script.md
    validation-plan.md

  apps/
    api/
      README.md
      src/
        crucible_api/
          __init__.py
          main.py
          settings.py
          routes/
            __init__.py
            runs.py
            assets.py
            health.py
          services/
            __init__.py
            run_service.py
            progress_stream.py
      tests/

    web/
      README.md
      next.config.ts
      package.json
      src/
        app/
          page.tsx
          runs/
            [runId]/
              page.tsx
        components/
          brief-form.tsx
          gauntlet-timeline.tsx
          candidate-grid.tsx
          verdict-panel.tsx
          hallmark-viewer.tsx
        lib/
          api.ts
          types.ts
      public/

  packages/
    crucible-core/
      README.md
      src/
        crucible/
          __init__.py
          config/
            __init__.py
            model_registry.py
            routing_policy.py
          generation/
            __init__.py
            fanout.py
            candidate.py
            genblaze_pipeline.py
          rubric/
            __init__.py
            compiler.py
            schema.py
          checks/
            __init__.py
            deterministic.py
            ocr.py
            safety.py
            brand.py
            ip_risk.py
          judge/
            __init__.py
            pairwise.py
            confidence.py
            live_judge.py
            gold_audit.py
            aggregation.py
          refinement/
            __init__.py
            prompt_rewriter.py
            memory.py
          certification/
            __init__.py
            hallmark.py
            canonicalize.py
            storage_receipt.py
            verifier.py
          storage/
            __init__.py
            b2_sink.py
            object_layout.py
            parquet_sink.py
          telemetry/
            __init__.py
            tracing.py
          validation/
            __init__.py
            metrics.py
            benchmarks.py
      tests/
        unit/
        integration/

    shared-types/
      README.md
      package.json
      src/
        hallmark.ts
        run.ts
        candidate.ts

  configs/
    models.yaml
    routing.yaml
    rubrics/
      ecommerce-product-shot.yaml
    storage.yaml
    judge.yaml

  scripts/
    run_local_api.ps1
    run_local_web.ps1
    seed_demo_data.py
    verify_hallmark.py
    export_eval_tables.py

  data/
    README.md
    fixtures/
      briefs/
      images/
    eval/
      labels/
      reports/

  examples/
    ecommerce-product-shot/
      brief.json
      expected-hallmark.json
      README.md

  infra/
    modal/
      app.py
    vercel/
      project.json
    b2/
      bucket-policy.md

  .github/
    workflows/
      api-tests.yml
      web-tests.yml
      lint.yml
```

## Top-Level Responsibilities

| Path | Purpose |
|---|---|
| `apps/api` | FastAPI service that exposes run creation, status, SSE progress, asset retrieval, and Hallmark lookup. |
| `apps/web` | Next.js dashboard for brief submission, gauntlet progress, candidate comparison, verdicts, and certification display. |
| `packages/crucible-core` | The main Python domain library. Owns generation fan-out, rubric compilation, checks, judging, refinement, certification, storage, and validation. |
| `packages/shared-types` | TypeScript types for frontend/API contracts, especially Hallmark, candidate, and run shapes. Can later be generated from Python schemas. |
| `configs` | Runtime-swappable model registry, routing policy, judge policy, storage settings, and v1 rubric definitions. |
| `scripts` | Local developer utilities and demo helpers. |
| `data` | Local fixtures, human labels, benchmark reports, and demo assets. Avoid committing generated production media unless small and intentional. |
| `examples` | Reproducible demo briefs and expected outputs for judging and hackathon reviewers. |
| `infra` | Deployment-specific files for Modal, Vercel, and Backblaze B2 setup notes. |
| `docs` | Product, architecture, validation, and demo documentation. |

## Core Python Package Boundaries

### `generation`

Owns the Genblaze-facing generation flow.

- Builds provider pipelines from `configs/models.yaml`.
- Runs best-of-N fan-out across GMICloud and Replicate.
- Invokes premium fallback providers only after quality misses.
- Returns `CandidateBundle` objects for each AgentLoop round.

### `rubric`

Compiles a creative brief into weighted, checkable criteria.

- Produces objective hard gates such as aspect ratio, background, text, and uncropped product checks.
- Produces softer subjective criteria only when needed.
- Logs rubric compiler `chat()` calls into Hallmark `llm_calls`.

### `checks`

Runs low-cost eligibility checks before expensive judging.

- Deterministic checks: dimensions, aspect ratio, file integrity, background, transparency.
- OCR checks: required text extraction and exact or normalized matching.
- Safety, brand, and IP-risk screening.

### `judge`

The central Crucible IP layer.

- Runs VLM criterion checks.
- Performs bidirectional pairwise candidate ranking.
- Randomizes candidate order and measures order symmetry.
- Computes confidence from observable agreement signals.
- Conditionally invokes Qwen adjudication.
- Runs GPT-4o gold audit on the winner.

### `refinement`

Owns prompt rewrite and attempt memory.

- Carries full attempt history and feedback into rewrite calls.
- Rewrites the prompt rather than appending failure notes.
- Caps refinement iterations according to optimization-pressure policy.

### `certification`

Builds and verifies Hallmark records.

- Defines the Hallmark schema.
- Performs RFC 8785-style canonicalization.
- Computes `asset_sha256` and `hallmark_sha256`.
- Produces append-only revocation records.
- Verifies sealed Hallmarks.

### `storage`

Owns Backblaze B2 and analytics outputs.

- Stores candidates, manifests, Hallmarks, storage receipts, and pairwise comparison logs.
- Writes Parquet evaluation tables for DuckDB analysis.
- Keeps observed B2 Object Lock metadata outside the hashed Hallmark body.

### `validation`

Owns trust measurement.

- Computes Cohen's kappa against human labels.
- Tracks live-vs-gold judge divergence.
- Computes within-run diversity.
- Produces reward-hacking and benchmark-drift reports.

## Suggested MVP Build Order

1. Create `packages/crucible-core` with schemas for `Candidate`, `CandidateBundle`, `RoundVerdict`, `Criterion`, and `Hallmark`.
2. Add a single-provider Genblaze generation path and B2 manifest storage.
3. Implement deterministic gates for file integrity, aspect ratio, and resolution.
4. Add the e-commerce rubric config and a minimal rubric compiler.
5. Add OCR for required text.
6. Implement a single live VLM judge returning Genblaze-compatible `EvaluationResult`.
7. Add best-of-N fan-out and pairwise ranking.
8. Add refinement memory and capped prompt rewriting.
9. Add Hallmark canonicalization, hashing, and B2 storage receipt handling.
10. Add FastAPI run orchestration and SSE progress.
11. Add the Next.js dashboard.
12. Add validation harnesses, gold audit, and demo reporting.

## Initial Milestone Structure

For the first working slice, only these paths need to exist:

```text
apps/api/
packages/crucible-core/
configs/
examples/ecommerce-product-shot/
scripts/
docs/
```

The frontend can wait until the backend produces real run events and Hallmark artifacts.

## Naming Conventions

- Use `run_id` for the full user-facing job.
- Use `round_id` or `iteration` for one AgentLoop generation round.
- Use `attempt_id` for an individual candidate inside a round.
- Use `asset_sha256` only in the Hallmark `integrity` block.
- Use `judge_confidence` for reliability of the judging process, not asset quality.
- Use `quality_score` for the selected asset's normalized rubric quality.

## Storage Shape

Recommended B2 object layout:

```text
runs/{run_id}/
  root-manifest.json
  hallmark.json
  hallmark-storage-receipt.json
  rounds/
    {iteration}/
      round-manifest.json
      candidates/
        {attempt_id}/
          asset.png
          metadata.json
          checks.json
  ranking/
    pairwise-comparisons.json
  audits/
    gold-audit.json
  tables/
    candidate-results.parquet
    criterion-results.parquet
    pairwise-comparisons.parquet
```

Cross-run audits should live separately so sealed Hallmarks are never edited:

```text
audits/{date}/
  diversity-collapse-report.json
  judge-divergence-report.json
```

## Repository Principles

- Keep Genblaze integration inside the core library, not scattered through API route handlers.
- Keep provider/model choices config-driven.
- Run cheap hard gates before OCR and VLM judging.
- Store every failed attempt, not only the winner.
- Treat IP-risk output as warning signals, not legal determinations.
- Keep Hallmark records append-only after sealing.
- Separate `quality_score` from `judge_confidence` everywhere.
- Make the e-commerce vertical excellent before generalizing to broader creative media.
