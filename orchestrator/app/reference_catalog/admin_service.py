"""Admin-managed reference template service."""

from __future__ import annotations

import re
import uuid
from typing import Any

from orchestrator.app.api.errors import raise_api_error
from orchestrator.app.api.schemas.references import AdminReferenceTemplateCreateRequest, AdminReferenceTemplateUpdateRequest
from orchestrator.app.db.repositories import assets as asset_repo
from orchestrator.app.db.repositories import reference_templates as reference_repo
from orchestrator.app.db.session import db_transaction
from orchestrator.app.db.workspace_scope import WorkspaceScopeForbidden, WorkspaceScopeRequired, resolve_workspace_scope
from orchestrator.app.reference_catalog.service import db_reference_template_from_row, reference_template_asset_url
from orchestrator.app.schemas.reference_catalog import ReferenceTemplate
from orchestrator.app.storage.url_policy import build_public_r2_url


def _normalize_terms(values: list[str] | None) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values or []:
        normalized = str(value).strip()
        key = normalized.lower()
        if not normalized or key in seen:
            continue
        seen.add(key)
        result.append(normalized)
    return result


def _template_id_for(category: str, title: str) -> str:
    slug_source = f"{category}-{title}".strip().lower()
    slug = re.sub(r"[^a-z0-9]+", "_", slug_source).strip("_")
    if not slug:
        slug = "reference"
    return f"ref_{slug[:32]}_{uuid.uuid4().hex[:8]}"


def _asset_ready(row: dict) -> bool:
    upload_status = ((row.get("metadata") or {}).get("upload") or {}).get("status")
    return upload_status == "ready"


def _resolve_workspace(workspace_id: str | None, user_id: str | None) -> str:
    try:
        return resolve_workspace_scope(workspace_id, user_id)
    except WorkspaceScopeRequired as exc:
        raise_api_error(400, "reference_workspace_required", "Workspace information is required.", detail=str(exc))
    except WorkspaceScopeForbidden as exc:
        raise_api_error(403, "reference_workspace_forbidden", "Workspace access denied.", detail=str(exc))


def create_admin_reference_template(
    request: AdminReferenceTemplateCreateRequest,
    *,
    user_id: str | None = None,
) -> ReferenceTemplate:
    resolved_user_id = user_id.strip() if user_id and user_id.strip() else None
    workspace_id = _resolve_workspace(request.workspace_id, resolved_user_id)

    with db_transaction() as conn:
        asset = asset_repo.get_asset_by_public_id(
            request.asset_id,
            workspace_id=workspace_id,
            created_by=resolved_user_id,
            connection=conn,
        )
        if not asset:
            raise_api_error(404, "reference_asset_not_found", "Reference upload asset was not found.")
        if asset.get("kind") != "reference":
            raise_api_error(400, "invalid_reference_asset_kind", "Reference template assets must use kind=reference.")
        if not _asset_ready(asset):
            raise_api_error(409, "reference_asset_not_ready", "Reference upload must be completed before creating a template.")

        object_key = str(asset.get("object_key") or "")
        if not object_key:
            raise_api_error(409, "reference_asset_missing_object_key", "Reference asset storage metadata is incomplete.")

        template_id = request.template_id or _template_id_for(request.category, request.title)
        source_image_path = f"r2://{object_key}"
        public_url = asset.get("public_url") or build_public_r2_url(object_key)
        metadata = {
            "permanent": True,
            "storage_provider": "r2",
            "copyright_status": request.copyright_status,
            "reference_asset_id": request.asset_id,
            "r2_object_key": object_key,
            "asset_public_id": request.asset_id,
            **(request.metadata or {}),
        }
        row = reference_repo.create_reference_template(
            {
                "template_id": template_id,
                "title": request.title,
                "description": request.description,
                "category": request.category,
                "sub_category": request.sub_category,
                "tags": _normalize_terms(request.tags),
                "business_types": _normalize_terms(request.business_types),
                "ad_formats": _normalize_terms(request.ad_formats),
                "platforms": _normalize_terms(request.platforms),
                "aspect_ratio": request.aspect_ratio,
                "width": asset.get("width"),
                "height": asset.get("height"),
                "asset_public_id": request.asset_id,
                "thumbnail_url": public_url,
                "preview_url": public_url,
                "source_image_path": source_image_path,
                "style_keywords": _normalize_terms(request.style_keywords),
                "color_palette": _normalize_terms(request.color_palette),
                "layout_hint": request.layout_hint,
                "typography_hint": request.typography_hint,
                "background_style": request.background_style,
                "popularity_score": request.popularity_score,
                "status": request.status,
                "source": "admin_upload",
                "license_note": request.license_note,
                "metadata": metadata,
                "created_by": resolved_user_id,
            },
            connection=conn,
        )
    return db_reference_template_from_row(row)


def list_admin_reference_templates(*, active_only: bool = False) -> list[ReferenceTemplate]:
    return [db_reference_template_from_row(row) for row in reference_repo.list_reference_templates(active_only=active_only)]


def update_admin_reference_template(template_id: str, request: AdminReferenceTemplateUpdateRequest) -> ReferenceTemplate | None:
    payload = request.model_dump(exclude_unset=True)
    for key in ("tags", "business_types", "ad_formats", "platforms", "style_keywords", "color_palette"):
        if key in payload:
            payload[key] = _normalize_terms(payload[key])
    row = reference_repo.update_reference_template(template_id, payload)
    return db_reference_template_from_row(row) if row else None


def publish_admin_reference_template(template_id: str) -> ReferenceTemplate | None:
    row = reference_repo.update_reference_template(template_id, {"status": "active"})
    return db_reference_template_from_row(row) if row else None


def unpublish_admin_reference_template(template_id: str) -> ReferenceTemplate | None:
    row = reference_repo.update_reference_template(template_id, {"status": "inactive"})
    return db_reference_template_from_row(row) if row else None


def admin_reference_payload(template: ReferenceTemplate) -> dict[str, Any]:
    card_url = reference_template_asset_url(template, "preview") or reference_template_asset_url(template, "thumbnail")
    return {
        **template.model_dump(mode="json"),
        "thumbnail_url": reference_template_asset_url(template, "thumbnail") or card_url,
        "preview_url": reference_template_asset_url(template, "preview") or card_url,
    }
