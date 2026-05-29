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
