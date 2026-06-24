# Crucible API

FastAPI wrapper around the Phase 0 Genblaze/B2 spine.

## Local Run

```powershell
python -m uvicorn crucible_api.main:app --app-dir apps/api/src --reload
```

Use `POST /runs` to generate and verify a Phase 0 asset. Use `dry_run: true` for no-network local smoke tests.
