"""Archive API routes."""

from __future__ import annotations

from fastapi import APIRouter, Query, status

from orchestrator.app.api.errors import raise_api_error
from orchestrator.app.api.schemas.archive import (
    ArchiveItemCreateRequest,
    ArchiveListResponse,
    ArchiveMutationResponse,
    ArchiveItemResponse,
)
from orchestrator.app.api.schemas.common import EmptyState, Pagination
from orchestrator.app.archive.service import (
    ArchiveItemNotFound,
    ArchivePersistenceUnavailable,
    ArchiveWorkspaceRequired,
    ArchiveWorkspaceForbidden,
    ArchiveGenerationOutputNotReady,
    ArchiveInvalidGeneratedSource,
    create_archive_item,
    delete_archive_item,
    get_archive_item,
    list_archive_items,
)

router = APIRouter()


def _archive_unavailable(error: Exception) -> None:
    raise_api_error(
        status_code=503,
        error_code="archive_storage_unavailable",
        message="Archive storage is not available.",
        detail=str(error),
    )


def _archive_workspace_required(error: Exception) -> None:
    raise_api_error(
        status_code=400,
        error_code="archive_workspace_required",
        message="Archive workspace information is required.",
        detail=str(error),
    )


def _archive_workspace_forbidden(error: Exception) -> None:
    raise_api_error(
        status_code=403,
        error_code="archive_workspace_forbidden",
        message="Archive workspace access denied.",
        detail=str(error),
    )


@router.post("/archive/items", response_model=ArchiveMutationResponse, status_code=status.HTTP_201_CREATED)
def create_archive_item_route(request: ArchiveItemCreateRequest) -> ArchiveMutationResponse:
    try:
        item = create_archive_item(request)
    except ArchivePersistenceUnavailable as exc:
        _archive_unavailable(exc)
    except ArchiveWorkspaceRequired as exc:
        _archive_workspace_required(exc)
    except ArchiveWorkspaceForbidden as exc:
        _archive_workspace_forbidden(exc)
    except ArchiveGenerationOutputNotReady as exc:
        raise_api_error(
            status_code=409,
            error_code="generation_output_not_ready",
            message="Generation output is not ready.",
            detail=str(exc),
        )
    except ArchiveInvalidGeneratedSource as exc:
        raise_api_error(
            status_code=400,
            error_code="invalid_generated_source",
            message="Invalid generated source.",
            detail=str(exc),
        )
    return ArchiveMutationResponse(item=item)


@router.get("/archive/items", response_model=ArchiveListResponse)
def list_archive_items_route(
    workspace_id: str | None = None,
    user_id: str | None = None,
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> ArchiveListResponse:
    try:
        items, total = list_archive_items(workspace_id=workspace_id, user_id=user_id, limit=limit, offset=offset)
    except ArchivePersistenceUnavailable as exc:
        _archive_unavailable(exc)
    except ArchiveWorkspaceRequired as exc:
        _archive_workspace_required(exc)
    except ArchiveWorkspaceForbidden as exc:
        _archive_workspace_forbidden(exc)
    empty_state = None
    if not items:
        empty_state = EmptyState(
            kind="no_archive_items",
            title="No saved archive items.",
            message="Saved generated ads will appear here.",
        )
    return ArchiveListResponse(
        items=items,
        pagination=Pagination(limit=limit, offset=offset, total=total, has_more=(offset + len(items)) < total),
        empty_state=empty_state,
    )


@router.get("/archive/items/{archive_item_id}", response_model=ArchiveItemResponse)
def get_archive_item_route(archive_item_id: str, workspace_id: str | None = None, user_id: str | None = None) -> ArchiveItemResponse:
    try:
        return get_archive_item(archive_item_id=archive_item_id, workspace_id=workspace_id, user_id=user_id)
    except ArchivePersistenceUnavailable as exc:
        _archive_unavailable(exc)
    except ArchiveWorkspaceRequired as exc:
        _archive_workspace_required(exc)
    except ArchiveWorkspaceForbidden as exc:
        _archive_workspace_forbidden(exc)
    except ArchiveItemNotFound:
        raise_api_error(
            status_code=404,
            error_code="archive_item_not_found",
            message="Archive item was not found.",
            detail=f"archive_item_id={archive_item_id}",
        )


@router.delete("/archive/items/{archive_item_id}", response_model=ArchiveMutationResponse)
def delete_archive_item_route(archive_item_id: str, workspace_id: str | None = None, user_id: str | None = None) -> ArchiveMutationResponse:
    try:
        item = delete_archive_item(archive_item_id=archive_item_id, workspace_id=workspace_id, user_id=user_id)
    except ArchivePersistenceUnavailable as exc:
        _archive_unavailable(exc)
    except ArchiveWorkspaceRequired as exc:
        _archive_workspace_required(exc)
    except ArchiveWorkspaceForbidden as exc:
        _archive_workspace_forbidden(exc)
    except ArchiveItemNotFound:
        raise_api_error(
            status_code=404,
            error_code="archive_item_not_found",
            message="Archive item was not found.",
            detail=f"archive_item_id={archive_item_id}",
        )
    return ArchiveMutationResponse(item=item)
