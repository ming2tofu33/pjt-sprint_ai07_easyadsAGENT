"""Reference catalog API routes."""

from __future__ import annotations

from typing import Annotated, NoReturn
from urllib.parse import quote

from fastapi import APIRouter, Query
from fastapi.responses import FileResponse
from pydantic import ValidationError

from orchestrator.app.api.errors import raise_api_error
from orchestrator.app.api.schemas.common import EmptyState, Pagination, RecoveryAction
from orchestrator.app.api.schemas.references import (
    AdminReferenceTemplateCreateRequest,
    AdminReferenceTemplateItemResponse,
    AdminReferenceTemplateListResponse,
    AdminReferenceTemplateUpdateRequest,
    ReferenceTemplateCardResponse,
    ReferenceTemplateDetailResponse,
    ReferenceTemplateListResponse,
    ReferenceTemplateSimilarResponse,
)
from orchestrator.app.reference_catalog.service import (
    find_similar_templates,
    get_reference_template,
    reference_template_asset_url,
    search_reference_templates,
    temporary_reference_asset_path,
    temporary_references_enabled,
)
from orchestrator.app.reference_catalog.admin_service import (
    admin_reference_payload,
    create_admin_reference_template,
    list_admin_reference_templates,
    publish_admin_reference_template,
    unpublish_admin_reference_template,
    update_admin_reference_template,
)
from orchestrator.app.schemas.reference_catalog import ReferenceTemplate, ReferenceTemplateSearchQuery

router = APIRouter()


def to_reference_card_response(template: ReferenceTemplate) -> ReferenceTemplateCardResponse:
    card = ReferenceTemplateCardResponse.from_template(template)
    card.thumbnail_url = reference_template_asset_url(template, "thumbnail")
    card.preview_url = reference_template_asset_url(template, "preview")
    return card


def _empty_reference_state() -> EmptyState:
    return EmptyState(
        kind="no_reference_templates",
        title="No matching reference templates",
        message="Try another keyword or clear filters.",
        suggested_actions=[
            RecoveryAction(action="clear_filters", label="Clear filters"),
        ],
    )


def _reference_detail(template: ReferenceTemplate) -> dict[str, object]:
    return {
        "style_keywords": template.style_keywords,
        "color_palette": template.color_palette,
        "layout_hint": template.layout_hint,
        "typography_hint": template.typography_hint,
        "background_style": template.background_style,
        "license_note": template.license_note,
        "metadata": template.metadata,
        "has_source_image": bool(template.assets.source_image_path),
    }


def _not_found(template_id: str) -> NoReturn:
    raise_api_error(
        status_code=404,
        error_code="reference_template_not_found",
        message="Reference template was not found.",
        detail=f"template_id={template_id}",
    )


@router.get("/references/temp-assets/{removal_group}/{filename}")
def get_temporary_reference_asset(removal_group: str, filename: str) -> FileResponse:
    if not temporary_references_enabled():
        raise_api_error(
            status_code=404,
            error_code="temporary_reference_assets_disabled",
            message="Temporary reference assets are disabled.",
            detail=f"removal_group={quote(removal_group, safe='')}",
        )

    asset_path = temporary_reference_asset_path(removal_group, filename)
    if not asset_path or not asset_path.is_file():
        raise_api_error(
            status_code=404,
            error_code="temporary_reference_asset_not_found",
            message="Temporary reference asset was not found.",
            detail=f"filename={quote(filename, safe='')}",
        )
    return FileResponse(asset_path)


@router.get("/references", response_model=ReferenceTemplateListResponse)
def list_references(
    keyword: str | None = None,
    category: str | None = None,
    business_type: str | None = None,
    ad_format: str | None = None,
    platform: str | None = None,
    aspect_ratio: str | None = None,
    tags: Annotated[list[str] | None, Query()] = None,
    style_keywords: Annotated[list[str] | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
    sort_by: str = "relevance",
    active_only: bool = True,
) -> ReferenceTemplateListResponse:
    try:
        query = ReferenceTemplateSearchQuery(
            keyword=keyword,
            category=category,
            business_type=business_type,
            ad_format=ad_format,
            platform=platform,
            aspect_ratio=aspect_ratio,
            tags=tags or [],
            style_keywords=style_keywords or [],
            limit=limit,
            offset=offset,
            sort_by=sort_by,
            active_only=active_only,
        )
        result = search_reference_templates(query)
    except ValidationError as exc:
        raise_api_error(
            status_code=400,
            error_code="invalid_reference_query",
            message="Invalid reference template query.",
            detail=str(exc),
        )

    items = [to_reference_card_response(template) for template in result.items]
    pagination = Pagination(
        limit=result.limit,
        offset=result.offset,
        total=result.total,
        has_more=result.offset + len(items) < result.total,
    )
    return ReferenceTemplateListResponse(
        items=items,
        pagination=pagination,
        empty_state=_empty_reference_state() if not items else None,
    )


@router.get("/references/{template_id}", response_model=ReferenceTemplateDetailResponse)
def get_reference_detail(template_id: str) -> ReferenceTemplateDetailResponse:
    template = get_reference_template(template_id)
    if not template:
        _not_found(template_id)

    similar = find_similar_templates(template_id, limit=4)
    return ReferenceTemplateDetailResponse(
        template=to_reference_card_response(template),
        detail=_reference_detail(template),
        similar_templates=[to_reference_card_response(item) for item in similar],
    )


@router.get("/references/{template_id}/similar", response_model=ReferenceTemplateSimilarResponse)
def get_similar_references(
    template_id: str,
    limit: Annotated[int, Query(ge=1, le=50)] = 8,
) -> ReferenceTemplateSimilarResponse:
    template = get_reference_template(template_id)
    if not template:
        _not_found(template_id)

    similar = find_similar_templates(template_id, limit=limit)
    return ReferenceTemplateSimilarResponse(
        template_id=template_id,
        items=[to_reference_card_response(item) for item in similar if item.template_id != template_id],
    )


def _admin_not_found(template_id: str) -> NoReturn:
    raise_api_error(
        status_code=404,
        error_code="admin_reference_template_not_found",
        message="Admin reference template was not found.",
        detail=f"template_id={template_id}",
    )


@router.get("/admin/references", response_model=AdminReferenceTemplateListResponse)
def list_admin_references(active_only: bool = False) -> AdminReferenceTemplateListResponse:
    templates = list_admin_reference_templates(active_only=active_only)
    return AdminReferenceTemplateListResponse(items=[admin_reference_payload(template) for template in templates])


@router.post("/admin/references", response_model=AdminReferenceTemplateItemResponse)
def create_admin_reference(
    request: AdminReferenceTemplateCreateRequest,
    user_id: str | None = None,
) -> AdminReferenceTemplateItemResponse:
    template = create_admin_reference_template(request, user_id=user_id)
    return AdminReferenceTemplateItemResponse(template=admin_reference_payload(template))


@router.patch("/admin/references/{template_id}", response_model=AdminReferenceTemplateItemResponse)
def update_admin_reference(
    template_id: str,
    request: AdminReferenceTemplateUpdateRequest,
) -> AdminReferenceTemplateItemResponse:
    template = update_admin_reference_template(template_id, request)
    if not template:
        _admin_not_found(template_id)
    return AdminReferenceTemplateItemResponse(template=admin_reference_payload(template))


@router.post("/admin/references/{template_id}/publish", response_model=AdminReferenceTemplateItemResponse)
def publish_admin_reference(template_id: str) -> AdminReferenceTemplateItemResponse:
    template = publish_admin_reference_template(template_id)
    if not template:
        _admin_not_found(template_id)
    return AdminReferenceTemplateItemResponse(template=admin_reference_payload(template))


@router.post("/admin/references/{template_id}/unpublish", response_model=AdminReferenceTemplateItemResponse)
def unpublish_admin_reference(template_id: str) -> AdminReferenceTemplateItemResponse:
    template = unpublish_admin_reference_template(template_id)
    if not template:
        _admin_not_found(template_id)
    return AdminReferenceTemplateItemResponse(template=admin_reference_payload(template))
