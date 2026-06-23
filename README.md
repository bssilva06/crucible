# Crucible

Crucible is an adversarial generate-and-certify gauntlet for AI media, built on Genblaze and Backblaze B2.

This repository is currently at **Phase 0: Spine**. The goal is to prove one generation path can create an asset, persist it to Backblaze B2, write a manifest, and verify the manifest hash against the stored asset.

## Phase 0 Scope

Included:

- Python project scaffold.
- Config-driven Phase 0 provider selection.
- Example e-commerce product-shot brief.
- Dry-run generator for no-network smoke tests.
- B2/S3-compatible storage adapter.
- Local manifest writer and verifier.
- Unit tests for config, object keys, hashing, and dry-run manifest verification.

Deferred:

- Hallmark certification.
- OCR.
- VLM judging.
- Pairwise ranking.
- Refinement.
- Parquet analytics.
- FastAPI.
- Next.js.

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
pytest
```
