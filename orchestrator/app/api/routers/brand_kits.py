"""BrandKit API routes."""

from __future__ import annotations

from typing import NoReturn

from fastapi import APIRouter

from orchestrator.app.api.errors import raise_api_error
from orchestrator.app.api.schemas.brand_kits import (
    BrandKitCreateRequest,
    BrandKitGetCurrentResponse,
    BrandKitMutationResponse,
    BrandKitUpdateRequest,
)
from orchestrator.app.api.schemas.common import EmptyState, RecoveryAction
from orchestrator.app.brand_kits.service import (
    create_brand_kit,
    get_brand_kit,
    get_current_brand_kit,
    update_brand_kit,
)

router = APIRouter()


def _empty_brand_kit_state() -> EmptyState:
    return EmptyState(
        kind="no_brand_kit",
        title="No saved brand kit",
        message="Save store details to reuse them in future ad generation.",
        suggested_actions=[
            RecoveryAction(action="create_brand_kit", label="Create brand kit"),
        ],
    )


def _not_found(brand_kit_id: str) -> NoReturn:
    raise_api_error(
        status_code=404,
        error_code="brand_kit_not_found",
        message="Brand kit was not found.",
        detail=f"brand_kit_id={brand_kit_id}",
    )


@router.get("/brand-kits/current", response_model=BrandKitGetCurrentResponse)
def get_current_brand_kit_route(user_id: str | None = None) -> BrandKitGetCurrentResponse:
    brand_kit = get_current_brand_kit(user_id)
    return BrandKitGetCurrentResponse(
        has_brand_kit=brand_kit is not None,
        brand_kit=brand_kit,
        empty_state=None if brand_kit else _empty_brand_kit_state(),
    )


@router.post("/brand-kits", response_model=BrandKitMutationResponse)
def create_brand_kit_route(request: BrandKitCreateRequest) -> BrandKitMutationResponse:
    return BrandKitMutationResponse(brand_kit=create_brand_kit(request))


@router.get("/brand-kits/{brand_kit_id}", response_model=BrandKitMutationResponse)
def get_brand_kit_route(brand_kit_id: str) -> BrandKitMutationResponse:
    brand_kit = get_brand_kit(brand_kit_id)
    if not brand_kit:
        _not_found(brand_kit_id)
    return BrandKitMutationResponse(brand_kit=brand_kit)


@router.patch("/brand-kits/{brand_kit_id}", response_model=BrandKitMutationResponse)
def update_brand_kit_route(brand_kit_id: str, request: BrandKitUpdateRequest) -> BrandKitMutationResponse:
    try:
        brand_kit = update_brand_kit(brand_kit_id, request)
    except ValueError as exc:
        raise_api_error(
            status_code=400,
            error_code="invalid_brand_kit_request",
            message="Invalid brand kit update request.",
            detail=str(exc),
        )
    if not brand_kit:
        _not_found(brand_kit_id)
    return BrandKitMutationResponse(brand_kit=brand_kit)
