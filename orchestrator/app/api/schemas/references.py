"""Reference catalog API DTOs."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

from orchestrator.app.api.schemas.common import ApiMeta, EmptyState, Pagination
from orchestrator.app.schemas.reference_catalog import ReferenceTemplate


class ReferenceTemplateCardResponse(BaseModel):
    template_id: str
    title: str
    description: str | None = None
    category: str
    tags: list[str]
    business_types: list[str]
    ad_formats: list[str]
    platforms: list[str]
    aspect_ratio: str | None = None
    thumbnail_url: str | None = None
    preview_url: str | None = None
    style_keywords: list[str]
    color_palette: list[str]
    layout_hint: str | None = None
    typography_hint: str | None = None
    popularity_score: float
    is_saved: bool = False

    @classmethod
    def from_template(cls, template: ReferenceTemplate, *, is_saved: bool = False) -> "ReferenceTemplateCardResponse":
        return cls(
            template_id=template.template_id,
            title=template.title,
            description=template.description,
            category=template.category,
            tags=template.tags,
            business_types=template.business_types,
            ad_formats=template.ad_formats,
            platforms=template.platforms,
            aspect_ratio=template.aspect_ratio,
            thumbnail_url=None,
            preview_url=None,
            style_keywords=template.style_keywords,
            color_palette=template.color_palette,
            layout_hint=template.layout_hint,
            typography_hint=template.typography_hint,
            popularity_score=template.popularity_score,
            is_saved=is_saved,
        )


class ReferenceTemplateListResponse(BaseModel):
    success: Literal[True] = True
    items: list[ReferenceTemplateCardResponse]
    pagination: Pagination
    empty_state: EmptyState | None = None
    meta: ApiMeta = Field(default_factory=ApiMeta)


class ReferenceTemplateDetailResponse(BaseModel):
    success: Literal[True] = True
    template: ReferenceTemplateCardResponse
    detail: dict[str, Any] = Field(default_factory=dict)
    similar_templates: list[ReferenceTemplateCardResponse] = Field(default_factory=list)
    meta: ApiMeta = Field(default_factory=ApiMeta)


class ReferenceTemplateSimilarResponse(BaseModel):
    success: Literal[True] = True
    template_id: str
    items: list[ReferenceTemplateCardResponse]
    meta: ApiMeta = Field(default_factory=ApiMeta)


class AdminReferenceTemplateCreateRequest(BaseModel):
    template_id: str | None = Field(default=None, alias="templateId")
    asset_id: str = Field(alias="assetId", min_length=1)
    workspace_id: str | None = Field(default=None, alias="workspaceId")
    title: str = Field(..., min_length=1)
    description: str | None = None
    category: str = Field(..., min_length=1)
    sub_category: str | None = Field(default=None, alias="subCategory")
    tags: list[str] = Field(default_factory=list)
    business_types: list[str] = Field(default_factory=list, alias="businessTypes")
    ad_formats: list[str] = Field(default_factory=list, alias="adFormats")
    platforms: list[str] = Field(default_factory=list)
    aspect_ratio: str | None = Field(default=None, alias="aspectRatio")
    style_keywords: list[str] = Field(default_factory=list, alias="styleKeywords")
    color_palette: list[str] = Field(default_factory=list, alias="colorPalette")
    layout_hint: str | None = Field(default=None, alias="layoutHint")
    typography_hint: str | None = Field(default=None, alias="typographyHint")
    background_style: str | None = Field(default=None, alias="backgroundStyle")
    popularity_score: float = Field(default=0.0, ge=0, alias="popularityScore")
    status: Literal["active", "inactive", "draft"] = "draft"
    license_note: str | None = Field(default=None, alias="licenseNote")
    copyright_status: str = Field(default="owned_or_licensed", alias="copyrightStatus")
    metadata: dict[str, Any] = Field(default_factory=dict)


class AdminReferenceTemplateUpdateRequest(BaseModel):
    title: str | None = None
    description: str | None = None
    category: str | None = None
    sub_category: str | None = Field(default=None, alias="subCategory")
    tags: list[str] | None = None
    business_types: list[str] | None = Field(default=None, alias="businessTypes")
    ad_formats: list[str] | None = Field(default=None, alias="adFormats")
    platforms: list[str] | None = None
    aspect_ratio: str | None = Field(default=None, alias="aspectRatio")
    style_keywords: list[str] | None = Field(default=None, alias="styleKeywords")
    color_palette: list[str] | None = Field(default=None, alias="colorPalette")
    layout_hint: str | None = Field(default=None, alias="layoutHint")
    typography_hint: str | None = Field(default=None, alias="typographyHint")
    background_style: str | None = Field(default=None, alias="backgroundStyle")
    popularity_score: float | None = Field(default=None, ge=0, alias="popularityScore")
    status: Literal["active", "inactive", "draft"] | None = None
    license_note: str | None = Field(default=None, alias="licenseNote")
    metadata: dict[str, Any] | None = None


class AdminReferenceTemplateItemResponse(BaseModel):
    template: dict[str, Any]


class AdminReferenceTemplateListResponse(BaseModel):
    success: Literal[True] = True
    items: list[dict[str, Any]]
    meta: ApiMeta = Field(default_factory=ApiMeta)
