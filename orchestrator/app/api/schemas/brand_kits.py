"""Brand kit API DTOs."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator

from orchestrator.app.api.schemas.common import ApiMeta, AssetRef, EmptyState


BrandToneValue = Literal["emotional", "warm_cozy", "premium", "clean", "cute", "trendy", "bold", "natural"]
BrandKitStatus = Literal["active", "inactive", "draft"]


class BrandProduct(BaseModel):
    name: str
    description: str | None = None
    is_representative: bool = False
    metadata: dict[str, Any] = Field(default_factory=dict)


class BrandKitResponse(BaseModel):
    brand_kit_id: str
    user_id: str | None = None
    store_name: str
    business_type: str
    region_text: str | None = None
    sns_handle: str | None = None
    logo_asset: AssetRef | None = None
    brand_tones: list[str] = Field(default_factory=list)
    brand_colors: list[str] = Field(default_factory=list)
    frequent_phrases: list[str] = Field(default_factory=list)
    representative_products: list[BrandProduct] = Field(default_factory=list)
    status: BrandKitStatus = "active"
    created_at: str | None = None
    updated_at: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class BrandKitCreateRequest(BaseModel):
    user_id: str | None = None
    store_name: str
    business_type: str
    region_text: str | None = None
    sns_handle: str | None = None
    brand_tones: list[str] = Field(default_factory=list)
    brand_colors: list[str] = Field(default_factory=list)
    frequent_phrases: list[str] = Field(default_factory=list)
    representative_products: list[BrandProduct] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("store_name", "business_type")
    @classmethod
    def non_empty(cls, value: str) -> str:
        if not value or not value.strip():
            raise ValueError("value must not be empty")
        return value.strip()

    @field_validator("brand_colors")
    @classmethod
    def color_values_start_with_hash(cls, values: list[str]) -> list[str]:
        for color in values:
            if not color.startswith("#"):
                raise ValueError("brand_colors must start with #")
        return values


class BrandKitUpdateRequest(BaseModel):
    store_name: str | None = None
    business_type: str | None = None
    region_text: str | None = None
    sns_handle: str | None = None
    brand_tones: list[str] | None = None
    brand_colors: list[str] | None = None
    frequent_phrases: list[str] | None = None
    representative_products: list[BrandProduct] | None = None
    metadata: dict[str, Any] | None = None

    @field_validator("store_name", "business_type")
    @classmethod
    def optional_non_empty(cls, value: str | None) -> str | None:
        if value is not None and not value.strip():
            raise ValueError("value must not be empty")
        return value.strip() if value is not None else value

    @field_validator("brand_colors")
    @classmethod
    def optional_colors_start_with_hash(cls, values: list[str] | None) -> list[str] | None:
        if values is None:
            return values
        for color in values:
            if not color.startswith("#"):
                raise ValueError("brand_colors must start with #")
        return values


class BrandKitGetCurrentResponse(BaseModel):
    success: Literal[True] = True
    has_brand_kit: bool
    brand_kit: BrandKitResponse | None = None
    empty_state: EmptyState | None = None
    meta: ApiMeta = Field(default_factory=ApiMeta)
