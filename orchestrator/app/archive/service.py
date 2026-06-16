"""Archive service layer."""

from __future__ import annotations

from datetime import datetime

from orchestrator.app.api.schemas.archive import ArchiveItemCreateRequest, ArchiveItemResponse, ArchiveItemUpdateRequest
from orchestrator.app.artifacts.service import browser_usable_url, sanitize_result_artifact_payload_for_api
from orchestrator.app.db import settings as db_settings
from orchestrator.app.db.errors import DatabaseConfigurationError
from orchestrator.app.db.repositories import archive_items as archive_item_repo
from orchestrator.app.db.repositories import chat_threads as thread_repo  # Backward-compatible test patch target.
from orchestrator.app.db.repositories import generation_jobs as job_repo
from orchestrator.app.db.repositories import generation_outputs as output_repo
from orchestrator.app.db.repositories import workspaces as workspace_repo
from orchestrator.app.db.session import db_transaction


class ArchivePersistenceUnavailable(RuntimeError):
    """Raised when archive persistence cannot be used in the current environment."""


class ArchiveWorkspaceRequired(ValueError):
    """Raised when no workspace can be resolved for an archive action."""


class ArchiveWorkspaceForbidden(PermissionError):
    """Raised when the workspace is not available for the user."""


class ArchiveItemNotFound(LookupError):
    """Raised when an archive item cannot be found for the current workspace."""


class ArchiveGenerationOutputNotReady(RuntimeError):
    """Raised when trying to sync a job that doesn't have a final generation output ready."""


class ArchiveInvalidGeneratedSource(ValueError):
    """Raised when a generated source is missing required properties like public_job_id."""


def _ensure_postgres_enabled() -> None:
    try:
        enabled = db_settings.is_postgres_enabled()
    except DatabaseConfigurationError as exc:
        raise ArchivePersistenceUnavailable(str(exc)) from exc
    if not enabled:
        raise ArchivePersistenceUnavailable("Postgres DB backend is not enabled.")


def _resolve_workspace_id(workspace_id: str | None, user_id: str | None = None, account_type: str | None = None) -> str:
    from orchestrator.app.db.workspace_scope import WorkspaceScopeForbidden, WorkspaceScopeRequired, resolve_workspace_scope

    try:
        if account_type:
            return resolve_workspace_scope(workspace_id, user_id, account_type=account_type)
        return resolve_workspace_scope(workspace_id, user_id)
    except WorkspaceScopeRequired as exc:
        raise ArchiveWorkspaceRequired(str(exc)) from exc
    except WorkspaceScopeForbidden as exc:
        raise ArchiveWorkspaceForbidden(str(exc)) from exc


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
    public_archive_id = row.get("public_archive_id")
    if not public_archive_id:
        raise ArchivePersistenceUnavailable("Archive public ID is missing.")

    thumbnail_url = browser_usable_url(row.get("thumbnail_public_url") or row.get("thumbnail_url"))
    image_url = browser_usable_url(row.get("asset_public_url") or row.get("image_url"))

    download_url = None
    if row.get("output_download_url"):
        download_url = browser_usable_url(row["output_download_url"])
    elif row.get("output_final_image_url"):
        download_url = browser_usable_url(row["output_final_image_url"])
    else:
        safe_payload = sanitize_result_artifact_payload_for_api(row.get("output_result_payload") or {})
        if safe_payload.get("download_url"):
            download_url = browser_usable_url(safe_payload["download_url"])
        elif safe_payload.get("final_image_url"):
            download_url = browser_usable_url(safe_payload["final_image_url"])

    if not image_url and download_url:
        image_url = download_url

    return ArchiveItemResponse(
        ad_id=public_archive_id,
        title=row.get("title", ""),
        job_id=row.get("j_public_job_id") or row.get("public_job_id"),
        output_id=row.get("public_output_id"),
        thread_id=row.get("public_thread_id"),
        thumbnail_url=thumbnail_url,
        image_url=image_url,
        download_url=download_url,
        status=row.get("status", "saved"),
        ad_format=row.get("ad_format"),
        platform=row.get("platform"),
        source=row.get("source", "generated"),
        is_final=row.get("is_final"),
        storage_provider=row.get("storage_provider"),
        mime_type=row.get("asset_mime_type"),
        width=row.get("asset_width"),
        height=row.get("asset_height"),
        created_at=_iso(row.get("saved_at") or row.get("created_at")),
        saved_at=_iso(row.get("saved_at")),
        metadata=row.get("metadata") or {},
    )


def create_archive_item(request: ArchiveItemCreateRequest) -> ArchiveItemResponse:
    _ensure_postgres_enabled()
    user_id = _resolve_user_id(request.user_id)
    workspace_id = _resolve_workspace_id(request.workspace_id, user_id=user_id, account_type=request.account_type)

    if request.source == "generated":
        if not request.public_job_id:
            raise ArchiveInvalidGeneratedSource("public_job_id is required for generated archive items.")

        job = job_repo.get_generation_job_db(public_job_id=request.public_job_id, workspace_id=workspace_id)
        if not job:
            raise ArchiveItemNotFound("Job not found")
        return sync_archive_for_job(workspace_id=workspace_id, internal_job_id=str(job["id"]))

    row = archive_item_repo.create_archive_item_row(
        workspace_id=workspace_id,
        created_by=user_id,
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


def list_archive_items(
    *,
    workspace_id: str | None = None,
    user_id: str | None = None,
    account_type: str | None = None,
    limit: int = 50,
    offset: int = 0,
    include_total: bool = True,
) -> tuple[list[ArchiveItemResponse], int]:
    _ensure_postgres_enabled()
    resolved_user_id = _resolve_user_id(user_id)
    resolved_workspace_id = _resolve_workspace_id(workspace_id, user_id=resolved_user_id, account_type=account_type)
    fetch_limit = limit + 1 if not include_total else limit
    rows = archive_item_repo.list_archive_item_rows(
        workspace_id=resolved_workspace_id,
        created_by=resolved_user_id,
        limit=fetch_limit,
        offset=offset,
    )
    visible_rows = rows[:limit]
    if include_total:
        total = archive_item_repo.count_archive_item_rows(workspace_id=resolved_workspace_id, created_by=resolved_user_id)
    else:
        total = offset + len(visible_rows) + (1 if len(rows) > limit else 0)
    return [archive_item_from_row(r) for r in visible_rows], total


def get_archive_item(
    *,
    archive_item_id: str,
    workspace_id: str | None = None,
    user_id: str | None = None,
    account_type: str | None = None,
) -> ArchiveItemResponse:
    _ensure_postgres_enabled()
    resolved_user_id = _resolve_user_id(user_id)
    resolved_workspace_id = _resolve_workspace_id(workspace_id, user_id=resolved_user_id, account_type=account_type)

    row = archive_item_repo.get_archive_item_row(
        public_archive_id=archive_item_id,
        workspace_id=resolved_workspace_id,
        created_by=resolved_user_id,
    )
    if not row:
        raise ArchiveItemNotFound("Archive item not found.")
    if row.get("source") == "generated":
        row = {
            **row,
            "title": row.get("thread_title") or row.get("title"),
            "metadata": {},
        }
    return archive_item_from_row(row)


def update_archive_item(*, archive_item_id: str, request: ArchiveItemUpdateRequest) -> ArchiveItemResponse:
    _ensure_postgres_enabled()
    resolved_user_id = _resolve_user_id(request.user_id)
    resolved_workspace_id = _resolve_workspace_id(request.workspace_id, user_id=resolved_user_id, account_type=request.account_type)
    row = archive_item_repo.update_archive_item_status_row(
        archive_item_id=archive_item_id,
        workspace_id=resolved_workspace_id,
        created_by=resolved_user_id,
        status=request.status,
    )
    if not row:
        raise ArchiveItemNotFound(f"archive_item_id={archive_item_id}")
    joined = archive_item_repo.get_archive_item_row(
        public_archive_id=row["public_archive_id"],
        workspace_id=resolved_workspace_id,
        created_by=resolved_user_id,
    )
    return archive_item_from_row(joined or row)


def delete_archive_item(
    *,
    archive_item_id: str,
    workspace_id: str | None = None,
    user_id: str | None = None,
    account_type: str | None = None,
) -> ArchiveItemResponse:
    _ensure_postgres_enabled()
    resolved_user_id = _resolve_user_id(user_id)
    resolved_workspace_id = _resolve_workspace_id(workspace_id, user_id=resolved_user_id, account_type=account_type)
    row = archive_item_repo.soft_delete_archive_item_row(
        archive_item_id=archive_item_id,
        workspace_id=resolved_workspace_id,
        created_by=resolved_user_id,
    )
    if not row:
        raise ArchiveItemNotFound(f"archive_item_id={archive_item_id}")
    return archive_item_from_row(row)


def sync_archive_for_job(workspace_id: str, internal_job_id: str, connection: object | None = None) -> ArchiveItemResponse:
    with db_transaction(connection) as conn:
        return _sync_archive_for_job(workspace_id=workspace_id, internal_job_id=internal_job_id, connection=conn)


def _sync_archive_for_job(workspace_id: str, internal_job_id: str, connection: object) -> ArchiveItemResponse:
    job = job_repo.get_generation_job_db_by_id(job_id=internal_job_id, workspace_id=workspace_id, connection=connection)
    if not job:
        raise ArchiveItemNotFound("Job not found")

    output = output_repo.get_final_generation_output_for_job(
        workspace_id=workspace_id,
        public_job_id=job["public_job_id"],
        connection=connection,
    )
    if not output:
        raise ArchiveGenerationOutputNotReady("Final generation output is not ready.")
    return _sync_archive_from_rows(workspace_id=workspace_id, job=job, output=output, connection=connection)


def _sync_archive_from_rows(*, workspace_id: str, job: dict, output: dict, connection: object) -> ArchiveItemResponse:
    public_job_id = job["public_job_id"]
    title = "Generated Ad"
    if job.get("thread_title"):
        title = job["thread_title"]
    elif job.get("brief") and job["brief"].get("item_or_service"):
        title = job["brief"]["item_or_service"]
    elif job.get("result_payload") and job["result_payload"].get("headline"):
        title = job["result_payload"]["headline"]

    request_payload = job.get("request_payload") or {}
    params = job.get("params") or {}
    metadata = job.get("metadata") or {}
    result_payload = job.get("result_payload") or {}

    ad_format = (
        params.get("ad_format")
        or request_payload.get("ad_format")
        or request_payload.get("adFormat")
        or metadata.get("ad_format")
        or result_payload.get("ad_format")
    )
    platform = (
        params.get("platform")
        or request_payload.get("platform")
        or metadata.get("platform")
        or result_payload.get("platform")
    )

    row = archive_item_repo.upsert_generated_archive_item_row(
        workspace_id=workspace_id,
        public_job_id=public_job_id,
        created_by=job.get("requested_by"),
        title=title,
        job_id=str(job["id"]),
        output_id=str(output["id"]),
        asset_id=str(output["asset_id"]) if output.get("asset_id") else None,
        thumbnail_url=output.get("thumbnail_url"),
        image_url=output.get("image_url"),
        status="saved",
        ad_format=ad_format,
        platform=platform,
        source="generated",
        connection=connection,
    )

    response_row = archive_item_repo.build_archive_response_row(
        row,
        public_job_id=public_job_id,
        public_thread_id=job.get("public_thread_id"),
        public_output_id=output.get("public_output_id"),
        is_final=True,
        image_url=output.get("image_url"),
        thumbnail_url=output.get("thumbnail_url"),
        output_download_url=output.get("output_download_url"),
        output_final_image_url=output.get("output_final_image_url"),
        storage_provider=output.get("storage_provider"),
        asset_mime_type=output.get("asset_mime_type"),
        asset_width=output.get("asset_width"),
        asset_height=output.get("asset_height"),
    )
    return archive_item_from_row(response_row)


def sync_archive_for_output(workspace_id: str, internal_output_id: str, connection: object | None = None) -> ArchiveItemResponse:
    with db_transaction(connection) as conn:
        return _sync_archive_for_output(workspace_id=workspace_id, internal_output_id=internal_output_id, connection=conn)


def _sync_archive_for_output(workspace_id: str, internal_output_id: str, connection: object) -> ArchiveItemResponse:
    output = output_repo.get_generation_output_by_id(output_id=internal_output_id, workspace_id=workspace_id, connection=connection)
    if not output:
        raise ArchiveGenerationOutputNotReady("Generation output not found.")
    if not output.get("job_id"):
        raise ArchiveGenerationOutputNotReady("Generation output not linked to a job.")

    job = job_repo.get_generation_job_db_by_id(job_id=str(output["job_id"]), workspace_id=workspace_id, connection=connection)
    if not job:
        raise ArchiveItemNotFound("Job not found")
    return _sync_archive_from_rows(workspace_id=workspace_id, job=job, output=output, connection=connection)
