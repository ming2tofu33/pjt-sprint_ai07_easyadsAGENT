"""Archive service layer."""

from __future__ import annotations

from datetime import datetime

from orchestrator.app.api.schemas.archive import ArchiveItemCreateRequest, ArchiveItemResponse
from orchestrator.app.db import settings as db_settings
from orchestrator.app.db.errors import DatabaseConfigurationError
from orchestrator.app.db.repositories import archive_items as archive_item_repo


class ArchivePersistenceUnavailable(RuntimeError):
    """Raised when archive persistence cannot be used in the current environment."""


class ArchiveWorkspaceRequired(ValueError):
    """Raised when no workspace can be resolved for archive persistence."""


class ArchiveItemNotFound(LookupError):
    """Raised when an archive item cannot be found for the current workspace."""


def _ensure_postgres_enabled() -> None:
    try:
        enabled = db_settings.is_postgres_enabled()
    except DatabaseConfigurationError as exc:
        raise ArchivePersistenceUnavailable(str(exc)) from exc
    if not enabled:
        raise ArchivePersistenceUnavailable("Postgres DB backend is not enabled.")


def _resolve_workspace_id(workspace_id: str | None) -> str:
    resolved = (workspace_id or db_settings.get_demo_workspace_id() or "").strip()
    if not resolved:
        raise ArchiveWorkspaceRequired("workspace_id or EASYADS_DEMO_WORKSPACE_ID is required.")
    return resolved


def _resolve_user_id(user_id: str | None) -> str | None:
    resolved = (user_id or db_settings.get_demo_user_id() or "").strip()
    return resolved or None


def _iso(value: object | None) -> str | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.isoformat()
    return str(value)


def archive_item_from_row(row: dict) -> ArchiveItemResponse:
    saved_at = _iso(row.get("saved_at"))
    return ArchiveItemResponse(
        ad_id=str(row["id"]),
        job_id=row.get("public_job_id"),
        title=row["title"],
        thumbnail_url=row.get("thumbnail_url"),
        image_url=row.get("image_url"),
        status=row.get("status") or "saved",
        ad_format=row.get("ad_format"),
        platform=row.get("platform"),
        source=row.get("source") or "generated",
        created_at=saved_at or _iso(row.get("created_at")),
        saved_at=saved_at,
        metadata=row.get("metadata") or {},
    )


def create_archive_item(request: ArchiveItemCreateRequest) -> ArchiveItemResponse:
    _ensure_postgres_enabled()
    workspace_id = _resolve_workspace_id(request.workspace_id)
    row = archive_item_repo.create_archive_item_row(
        workspace_id=workspace_id,
        created_by=_resolve_user_id(request.user_id),
        title=request.title.strip(),
        public_job_id=request.public_job_id,
        thumbnail_url=request.thumbnail_url,
        image_url=request.image_url,
        status=request.status,
        ad_format=request.ad_format,
        platform=request.platform,
        source=request.source,
        metadata=request.metadata,
    )
    return archive_item_from_row(row)


def list_archive_items(*, workspace_id: str | None = None, limit: int = 50, offset: int = 0) -> tuple[list[ArchiveItemResponse], int]:
    _ensure_postgres_enabled()
    resolved_workspace_id = _resolve_workspace_id(workspace_id)
    rows = archive_item_repo.list_archive_item_rows(
        workspace_id=resolved_workspace_id,
        limit=limit,
        offset=offset,
    )
    total = archive_item_repo.count_archive_item_rows(workspace_id=resolved_workspace_id)
    return [archive_item_from_row(row) for row in rows], total


def delete_archive_item(*, archive_item_id: str, workspace_id: str | None = None) -> ArchiveItemResponse:
    _ensure_postgres_enabled()
    resolved_workspace_id = _resolve_workspace_id(workspace_id)
    row = archive_item_repo.soft_delete_archive_item_row(
        archive_item_id=archive_item_id,
        workspace_id=resolved_workspace_id,
    )
    if not row:
        raise ArchiveItemNotFound(f"archive_item_id={archive_item_id}")
    return archive_item_from_row(row)
