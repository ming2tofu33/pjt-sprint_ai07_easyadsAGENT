"""Reference template catalog schemas."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator


ReferenceTemplateStatus = Literal["active", "inactive", "draft"]
ReferenceTemplateSource = Literal["seed", "admin_upload", "system", "external_placeholder"]
ReferenceTemplateSortKey = Literal["popular", "recent", "title", "relevance"]


class ReferenceTemplateAsset(BaseModel):
    thumbnail_path: str | None = None
    preview_path: str | None = None
    source_image_path: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class ReferenceTemplate(BaseModel):
    template_id: str
    title: str
    description: str | None = None
    category: str
    sub_category: str | None = None
    tags: list[str] = Field(default_factory=list)
    business_types: list[str] = Field(default_factory=list)
    ad_formats: list[str] = Field(default_factory=list)
    platforms: list[str] = Field(default_factory=list)
    aspect_ratio: str | None = None
    width: int | None = Field(default=None, ge=1)
    height: int | None = Field(default=None, ge=1)
    assets: ReferenceTemplateAsset = Field(default_factory=ReferenceTemplateAsset)
    style_keywords: list[str] = Field(default_factory=list)
    color_palette: list[str] = Field(default_factory=list)
    layout_hint: str | None = None
    typography_hint: str | None = None
    background_style: str | None = None
    popularity_score: float = Field(default=0.0, ge=0.0)
    status: ReferenceTemplateStatus = "active"
    source: ReferenceTemplateSource = "seed"
    license_note: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("template_id", "title", "category")
    @classmethod
    def non_empty(cls, value: str) -> str:
        if not value or not value.strip():
            raise ValueError("value must not be empty")
        return value.strip()


class ReferenceTemplateSearchQuery(BaseModel):
    keyword: str | None = None
    category: str | None = None
    business_type: str | None = None
    ad_format: str | None = None
    platform: str | None = None
    aspect_ratio: str | None = None
    tags: list[str] = Field(default_factory=list)
    style_keywords: list[str] = Field(default_factory=list)
    limit: int = Field(default=20, ge=1, le=100)
    offset: int = Field(default=0, ge=0)
    sort_by: ReferenceTemplateSortKey = "relevance"
    active_only: bool = True


class ReferenceTemplateSearchResult(BaseModel):
    items: list[ReferenceTemplate]
    total: int = Field(..., ge=0)
    limit: int = Field(..., ge=1)
    offset: int = Field(..., ge=0)
    query: ReferenceTemplateSearchQuery
    metadata: dict[str, Any] = Field(default_factory=dict)


class ReferenceTemplateDetail(BaseModel):
    template: ReferenceTemplate
    similar_templates: list[ReferenceTemplate] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class ReferenceTemplateSelection(BaseModel):
    template_id: str
    resolved_template: ReferenceTemplate | None = None
    reference_image_path: str | None = None
    style_profile_hint: dict[str, Any] = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("template_id")
    @classmethod
    def template_id_not_empty(cls, value: str) -> str:
        if not value or not value.strip():
            raise ValueError("template_id must not be empty")
        return value.strip()
