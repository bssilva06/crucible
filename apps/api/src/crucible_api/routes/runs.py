from __future__ import annotations

from fastapi import APIRouter, HTTPException, Response

from crucible_api.services.run_service import (
    RunCreateRequest,
    RunResponse,
    RunServiceError,
    get_run_service,
)

router = APIRouter(prefix="/runs", tags=["runs"])


@router.post("", response_model=RunResponse)
def create_run(request: RunCreateRequest) -> RunResponse:
    service = get_run_service()
    try:
        return service.create_run(request)
    except RunServiceError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/{run_id}", response_model=RunResponse)
def get_run(run_id: str) -> RunResponse:
    service = get_run_service()
    record = service.get_run(run_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Run not found")
    return record


@router.get("/{run_id}/asset")
def get_asset(run_id: str) -> Response:
    service = get_run_service()
    try:
        data, mime_type = service.get_asset(run_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Run not found") from exc
    except RunServiceError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return Response(content=data, media_type=mime_type)
