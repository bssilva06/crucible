# Crucible

Crucible is an adversarial generate-and-certify gauntlet for AI media, built on Genblaze and Backblaze B2.

This repository is currently at **Phase 1C: Brief-Aware Gemini Judge**. The pipeline can generate one asset, persist it to Backblaze B2, verify the manifest hash, run deterministic quality gates, and optionally run a Gemini vision judge against the prompt.

## Current Scope

Included:

- Python project scaffold.
- Config-driven Phase 0 provider selection.
- Example e-commerce product-shot brief.
- Dry-run generator for no-network smoke tests.
- B2/S3-compatible storage adapter.
- Local manifest writer and verifier.
- Unit tests for config, object keys, hashing, and dry-run manifest verification.
- Deterministic product-shot quality gates.
- Optional Gemini brief-aware VLM judging.
- FastAPI run endpoint and Next.js local app.

Deferred:

- Hallmark certification.
- OCR.
- Pairwise ranking.
- Refinement.
- Parquet analytics.

## Setup

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
```

For live Genblaze generation, also install the relevant Genblaze adapter packages once confirmed from the Genblaze docs:

```powershell
python -m pip install -e ".[genblaze-gmicloud]"
```

For live Gemini judging, also install:

```powershell
python -m pip install -e ".[gemini-judge]"
```

## Environment

Copy `.env.example` to `.env` and fill in real values locally. Do not commit `.env`.

Required for live B2 upload:

- `B2_APPLICATION_KEY_ID`
- `B2_APPLICATION_KEY`
- `B2_BUCKET_NAME`
- `B2_BUCKET_REGION`
- `B2_ENDPOINT_URL`

Required for default live generation:

- `GMICLOUD_API_KEY`

Required for live Gemini judging:

- `GEMINI_API_KEY` or `GOOGLE_API_KEY`

## Dry Run

Dry run does not call Genblaze or B2. It generates deterministic fixture bytes, writes to local temp storage, writes a manifest, and verifies the manifest.

```powershell
python scripts/phase0_generate.py --brief examples/ecommerce-product-shot/brief.json --dry-run
```

Then verify the printed run ID:

```powershell
python scripts/verify_manifest.py --run-id <run_id> --dry-run
```

## Live Phase 0 Command

```powershell
python scripts/phase0_generate.py --brief examples/ecommerce-product-shot/brief.json
```

Expected output includes:

- `run_id`
- `asset_uri`
- `manifest_uri`
- `asset_sha256`

Verify:

```powershell
python scripts/verify_manifest.py --run-id <run_id>
```

The live Genblaze adapter is intentionally narrow. If the installed Genblaze SDK surface differs from the adapter, update only `crucible/phase0/generator.py`.

## Tests

```powershell
pytest
```

Live tests are opt-in:

```powershell
$env:CRUCIBLE_RUN_LIVE_PROVIDER_TESTS="true"
$env:CRUCIBLE_RUN_LIVE_JUDGE_TESTS="true"
pytest
```

## Phase 0.5 Local API

```powershell
python -m uvicorn crucible_api.main:app --app-dir apps/api/src --reload
```

Useful endpoints:

- `GET http://localhost:8000/health`
- `POST http://localhost:8000/runs`
- `GET http://localhost:8000/runs/{run_id}`
- `GET http://localhost:8000/runs/{run_id}/asset`

Dry-run request:

```powershell
Invoke-RestMethod -Method Post -Uri http://localhost:8000/runs -ContentType "application/json" -Body '{"prompt":"Centered product bottle on white background","dry_run":true}'
```

## Phase 0.5 Local Web App

```powershell
cd apps/web
npm install
npm run dev
```

Open `http://localhost:3000`.

The frontend uses `NEXT_PUBLIC_API_BASE_URL` and must never receive provider or B2 secrets.

## Deployment Targets

- Backend: Modal, using `infra/modal/app.py`
- Frontend: Vercel, with `apps/web` as the project root
- Storage: Backblaze B2

Modal should hold all provider and B2 secrets. Vercel should only receive `NEXT_PUBLIC_API_BASE_URL`.
