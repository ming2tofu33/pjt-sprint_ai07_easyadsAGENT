"""In-memory BrandKit service skeleton."""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from orchestrator.app.api.schemas.brand_kits import (
    BrandKitCreateRequest,
    BrandKitResponse,
    BrandKitUpdateRequest,
)

DEMO_USER_ID = "demo_user"

_BRAND_KITS: dict[str, BrandKitResponse] = {}
_USER_CURRENT_BRAND_KIT: dict[str, str] = {}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _normalize_user_id(user_id: str | None) -> str:
    return user_id.strip() if user_id and user_id.strip() else DEMO_USER_ID


def create_brand_kit(request: BrandKitCreateRequest) -> BrandKitResponse:
    now = _now_iso()
    user_id = _normalize_user_id(request.user_id)
    brand_kit_id = f"bk_{uuid4().hex}"
    brand_kit = BrandKitResponse(
        brand_kit_id=brand_kit_id,
        user_id=user_id,
        store_name=request.store_name,
        business_type=request.business_type,
        region_text=request.region_text,
        sns_handle=request.sns_handle,
        brand_tones=request.brand_tones,
        brand_colors=request.brand_colors,
        frequent_phrases=request.frequent_phrases,
        representative_products=request.representative_products,
        created_at=now,
        updated_at=now,
        metadata=request.metadata,
    )
    _BRAND_KITS[brand_kit_id] = brand_kit
    _USER_CURRENT_BRAND_KIT[user_id] = brand_kit_id
    return brand_kit


def get_brand_kit(brand_kit_id: str) -> BrandKitResponse | None:
    return _BRAND_KITS.get(brand_kit_id)


def get_current_brand_kit(user_id: str | None = None) -> BrandKitResponse | None:
    brand_kit_id = _USER_CURRENT_BRAND_KIT.get(_normalize_user_id(user_id))
    return _BRAND_KITS.get(brand_kit_id) if brand_kit_id else None


def update_brand_kit(brand_kit_id: str, request: BrandKitUpdateRequest) -> BrandKitResponse | None:
    existing = get_brand_kit(brand_kit_id)
    if not existing:
        return None

    updates = request.model_dump(exclude_unset=True)
    if updates.get("store_name") is not None and not str(updates["store_name"]).strip():
        raise ValueError("store_name must not be empty")
    if updates.get("business_type") is not None and not str(updates["business_type"]).strip():
        raise ValueError("business_type must not be empty")

    normalized_updates = {key: value for key, value in updates.items() if value is not None}
    if "store_name" in normalized_updates:
        normalized_updates["store_name"] = str(normalized_updates["store_name"]).strip()
    if "business_type" in normalized_updates:
        normalized_updates["business_type"] = str(normalized_updates["business_type"]).strip()
    normalized_updates["updated_at"] = _now_iso()

    updated = existing.model_copy(update=normalized_updates)
    _BRAND_KITS[brand_kit_id] = updated
    if updated.user_id:
        _USER_CURRENT_BRAND_KIT[_normalize_user_id(updated.user_id)] = brand_kit_id
    return updated


def reset_brand_kit_store_for_tests() -> None:
    _BRAND_KITS.clear()
    _USER_CURRENT_BRAND_KIT.clear()
