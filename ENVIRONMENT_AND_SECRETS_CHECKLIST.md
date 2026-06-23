# Crucible Environment and Secrets Checklist

This checklist covers the environment variables, service accounts, local files, and operational secrets needed to build and demo Crucible.

Do not commit real secrets. Keep committed examples in `.env.example`, and keep real values in local `.env`, deployment secret stores, or CI/CD secret managers.

## Local Files

```text
.env.example          # committed template, no real secrets
.env                  # local developer secrets, ignored by git
configs/models.yaml   # model names, provider routing, no API keys
configs/routing.yaml  # quality/cost/latency routing policy
configs/storage.yaml  # bucket names and non-secret storage settings
```

## Required For Phase 0

These are the minimum variables needed to prove the Genblaze to Backblaze B2 spine.

```bash
CRUCIBLE_ENV=local
CRUCIBLE_LOG_LEVEL=INFO

B2_APPLICATION_KEY_ID=
B2_APPLICATION_KEY=
B2_BUCKET_NAME=
B2_BUCKET_REGION=
B2_ENDPOINT_URL=
B2_OBJECT_LOCK_ENABLED=true
B2_OBJECT_LOCK_MODE=governance
B2_OBJECT_LOCK_RETENTION_DAYS=30
```

Checklist:

- [ ] Create a Backblaze B2 bucket for development.
- [ ] Enable Object Lock on the bucket if testing certification storage.
- [ ] Create a scoped B2 application key for the bucket.
- [ ] Confirm the key can upload, read, and list objects.
- [ ] Confirm Object Lock metadata is visible after upload.
- [ ] Store bucket name and endpoint in config or env.
- [ ] Store key ID and application key only in secrets.

## Generation Providers

Use at least one provider for the first slice, then add the second core provider for fan-out.

```bash
GMICLOUD_API_KEY=
REPLICATE_API_TOKEN=
GOOGLE_API_KEY=
```

Checklist:

- [ ] GMICloud key is available for hackathon-credit generation.
- [ ] Replicate token is available for low-cost fan-out.
- [ ] Google API key is available only if using Imagen fallback or Gemini judge.
- [ ] Provider models are declared in `configs/models.yaml`.
- [ ] Premium fallback models are marked as fallback-only, not default fan-out.
- [ ] Per-provider spend limits are configured where the provider supports them.

## Judge And LLM Providers

```bash
GEMINI_API_KEY=
OPENAI_API_KEY=
QWEN_API_KEY=
```

Checklist:

- [ ] Gemini key is available for the live judge.
- [ ] OpenAI key is available for GPT-4o gold audit and optional prompt rewriting.
- [ ] Qwen endpoint/key is available if conditional adjudication is enabled.
- [ ] Judge models and versions are declared in `configs/judge.yaml`.
- [ ] Cross-family judging rules are encoded in config.
- [ ] Gold audit is enabled for certified and needs-review winners.
- [ ] LLM call logging records model, version, prompt hash, output hash, token usage, cost, and timestamp.

## OCR

PaddleOCR may not require a hosted API key, but it does require local/runtime dependencies and model downloads.

```bash
PADDLEOCR_LANG=en
PADDLEOCR_MODEL_DIR=
PADDLEOCR_ENABLE_GPU=false
```

Checklist:

- [ ] PaddleOCR dependency is installed in the backend environment.
- [ ] English OCR model works locally.
- [ ] Spanish OCR model is available if testing bilingual flows.
- [ ] OCR model files are cached in a known runtime path.
- [ ] OCR results are logged as criterion evidence without leaking unrelated image metadata.

## FastAPI Backend

```bash
API_HOST=127.0.0.1
API_PORT=8000
API_CORS_ORIGINS=http://localhost:3000
API_RUN_TIMEOUT_SECONDS=900
API_MAX_CANDIDATES_PER_ROUND=8
API_MAX_REFINEMENT_ITERATIONS=3
API_ENABLE_SSE=true
```

Checklist:

- [ ] Local API starts without provider calls.
- [ ] Health endpoint does not expose secrets.
- [ ] CORS allows the local Next.js frontend.
- [ ] Run timeout exceeds worst-case image generation time.
- [ ] Candidate and iteration caps match the reward-hacking mitigation policy.
- [ ] SSE progress stream redacts prompts only if prompt privacy mode is enabled.

## Frontend

Only expose public, non-secret values with `NEXT_PUBLIC_`.

```bash
NEXT_PUBLIC_API_BASE_URL=http://localhost:8000
NEXT_PUBLIC_APP_ENV=local
```

Checklist:

- [ ] No provider keys are present in frontend environment variables.
- [ ] No B2 application keys are present in frontend environment variables.
- [ ] Frontend talks only to the Crucible API, not directly to provider APIs.
- [ ] Hallmark viewer can render redacted records if needed.

## Optional Metadata/Auth

If Supabase is used for app metadata or auth, B2 remains the source of truth for sealed artifacts.

```bash
SUPABASE_URL=
SUPABASE_ANON_KEY=
SUPABASE_SERVICE_ROLE_KEY=
DATABASE_URL=
```

Checklist:

- [ ] `SUPABASE_ANON_KEY` is the only Supabase key allowed in frontend env.
- [ ] `SUPABASE_SERVICE_ROLE_KEY` is backend-only.
- [ ] Database stores indexes and user metadata, not canonical Hallmark truth.
- [ ] Run records link to B2 Hallmark URIs and hashes.

## Observability

```bash
OTEL_SERVICE_NAME=crucible-api
OTEL_EXPORTER_OTLP_ENDPOINT=
OTEL_EXPORTER_OTLP_HEADERS=
HONEYCOMB_API_KEY=
JAEGER_ENDPOINT=
```

Checklist:

- [ ] Local logging works without external observability services.
- [ ] Provider request IDs are included in traces.
- [ ] Run IDs, round IDs, and attempt IDs are included in logs.
- [ ] API keys, prompts, and raw images are not written to traces unless explicitly allowed.
- [ ] Cost and latency metrics are emitted per provider/model.

## Deployment: Modal

```bash
MODAL_TOKEN_ID=
MODAL_TOKEN_SECRET=
MODAL_ENVIRONMENT=main
```

Checklist:

- [ ] Modal secrets contain backend-only provider keys.
- [ ] Modal image includes Genblaze, OCR, and image-processing dependencies.
- [ ] Long-running generation jobs fit within configured Modal timeout.
- [ ] B2 credentials are available to the Modal app.
- [ ] Deployment logs do not print env vars.

## Deployment: Vercel

```bash
VERCEL_TOKEN=
VERCEL_ORG_ID=
VERCEL_PROJECT_ID=
```

Checklist:

- [ ] Vercel project has only frontend-safe env vars.
- [ ] Production API base URL points to deployed FastAPI backend.
- [ ] Preview deployments use preview API or clearly marked local/mock data.

## CI/CD

```bash
GITHUB_TOKEN=
CI=true
```

Checklist:

- [ ] CI can run unit tests without real provider keys.
- [ ] Integration tests requiring provider keys are opt-in.
- [ ] Secret scanning is enabled.
- [ ] `.env` is ignored by git.
- [ ] Test fixtures use fake credentials and fake B2 URIs.

## Secret Handling Rules

- [ ] Never commit `.env`.
- [ ] Never commit provider API keys, B2 keys, Supabase service keys, Modal tokens, or Vercel tokens.
- [ ] Never expose backend secrets through `NEXT_PUBLIC_` variables.
- [ ] Never include raw secrets in Hallmark records, manifests, traces, logs, screenshots, or demo videos.
- [ ] Hash prompts and LLM outputs in Hallmark records when full text should not be public.
- [ ] Store full prompt/evidence artifacts only when privacy policy allows it.
- [ ] Rotate any key that appears in git history, terminal recordings, logs, or screenshots.
- [ ] Use separate dev, demo, and production keys.
- [ ] Prefer least-privilege B2 application keys scoped to one bucket.

## `.env.example`

```bash
# Runtime
CRUCIBLE_ENV=local
CRUCIBLE_LOG_LEVEL=INFO

# API
API_HOST=127.0.0.1
API_PORT=8000
API_CORS_ORIGINS=http://localhost:3000
API_RUN_TIMEOUT_SECONDS=900
API_MAX_CANDIDATES_PER_ROUND=8
API_MAX_REFINEMENT_ITERATIONS=3
API_ENABLE_SSE=true

# Frontend
NEXT_PUBLIC_API_BASE_URL=http://localhost:8000
NEXT_PUBLIC_APP_ENV=local

# Backblaze B2
B2_APPLICATION_KEY_ID=
B2_APPLICATION_KEY=
B2_BUCKET_NAME=
B2_BUCKET_REGION=
B2_ENDPOINT_URL=
B2_OBJECT_LOCK_ENABLED=true
B2_OBJECT_LOCK_MODE=governance
B2_OBJECT_LOCK_RETENTION_DAYS=30

# Generation providers
GMICLOUD_API_KEY=
REPLICATE_API_TOKEN=
GOOGLE_API_KEY=

# Judges and LLMs
GEMINI_API_KEY=
OPENAI_API_KEY=
QWEN_API_KEY=

# OCR
PADDLEOCR_LANG=en
PADDLEOCR_MODEL_DIR=
PADDLEOCR_ENABLE_GPU=false

# Optional metadata/auth
SUPABASE_URL=
SUPABASE_ANON_KEY=
SUPABASE_SERVICE_ROLE_KEY=
DATABASE_URL=

# Observability
OTEL_SERVICE_NAME=crucible-api
OTEL_EXPORTER_OTLP_ENDPOINT=
OTEL_EXPORTER_OTLP_HEADERS=
HONEYCOMB_API_KEY=
JAEGER_ENDPOINT=

# Deployment
MODAL_TOKEN_ID=
MODAL_TOKEN_SECRET=
MODAL_ENVIRONMENT=main
VERCEL_TOKEN=
VERCEL_ORG_ID=
VERCEL_PROJECT_ID=
```

## Pre-Demo Verification

- [ ] Run one generation using the core provider.
- [ ] Confirm candidate asset uploaded to B2.
- [ ] Confirm Genblaze manifest uploaded to B2.
- [ ] Confirm Hallmark uploaded to B2.
- [ ] Confirm Hallmark hash verifies after download.
- [ ] Confirm Object Lock receipt is stored separately.
- [ ] Confirm frontend displays no secret-bearing fields.
- [ ] Confirm logs and traces include run IDs but no API keys.
- [ ] Confirm provider spend limits are acceptable for the live demo.
- [ ] Rotate demo keys after the hackathon if they were used live.
