"""Asset API router."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends

from orchestrator.app.api.schemas.assets import (
    AssetPresignRequest,
    AssetPresignResponse,
    AssetCompleteResponse,
    AssetGetResponse,
)
from orchestrator.app.assets import service

router = APIRouter(prefix="/assets", tags=["Assets"])


from orchestrator.app.api.errors import raise_api_error
from orchestrator.app.assets.errors import AssetServiceError, NotFoundError

def _handle_asset_error(exc: Exception):
    if isinstance(exc, AssetServiceError):
        raise_api_error(status_code=exc.status_code, error_code=exc.error_code, message=exc.message)
    raise exc

@router.post("/uploads/presign", response_model=AssetPresignResponse)
def presign_asset_upload(req: AssetPresignRequest) -> Any:
    try:
        return service.presign_asset_upload(req)
    except Exception as exc:
        _handle_asset_error(exc)


@router.post("/uploads/{asset_id}/complete", response_model=AssetCompleteResponse)
def complete_asset_upload(asset_id: str) -> Any:
    try:
        res = service.complete_asset_upload(public_asset_id=asset_id)
        return AssetCompleteResponse(asset=res)
    except Exception as exc:
        _handle_asset_error(exc)


@router.get("/{asset_id}", response_model=AssetGetResponse)
def get_asset(asset_id: str) -> Any:
    try:
        res = service.get_asset_response(public_asset_id=asset_id)
        return AssetGetResponse(asset=res)
    except Exception as exc:
        _handle_asset_error(exc)
