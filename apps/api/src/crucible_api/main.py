from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from crucible_api.routes.health import router as health_router
from crucible_api.routes.runs import router as runs_router
from crucible_api.settings import ApiSettings


settings = ApiSettings.load()

app = FastAPI(title="Crucible API", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)
app.include_router(health_router)
app.include_router(runs_router)
