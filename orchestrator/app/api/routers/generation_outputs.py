"""Generation Outputs API routes."""

from __future__ import annotations

from fastapi import APIRouter, Query, status

from orchestrator.app.api.errors import raise_api_error
from orchestrator.app.api.schemas.generation_outputs import (
    GenerationOutputListResponse,
    GenerationOutputResponse,
)
from orchestrator.app.api.schemas.common import EmptyState, Pagination
from orchestrator.app.generation_outputs.service import (
    GenerationOutputNotFound,
    GenerationOutputPersistenceUnavailable,
    get_generation_output,
    list_generation_outputs,
    select_final_generation_output,
)

router = APIRouter()


@router.get("/generation-outputs", response_model=GenerationOutputListResponse)
def list_generation_outputs_route(
    workspace_id: str | None = None,
    threadId: str | None = None,
    jobId: str | None = None,
    isFinal: bool | None = None,
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    user_id: str | None = None,
) -> GenerationOutputListResponse:
    from orchestrator.app.db.workspace_scope import resolve_workspace_scope, WorkspaceScopeForbidden, WorkspaceScopeRequired
    try:
        workspace_id = resolve_workspace_scope(workspace_id, user_id=user_id)
    except WorkspaceScopeForbidden as e:
        raise_api_error(403, "workspace_forbidden", "Workspace access denied.", detail=str(e))
    except WorkspaceScopeRequired as e:
        raise_api_error(400, "workspace_required", "Workspace is required.", detail=str(e))
    try:
        items, total = list_generation_outputs(
            workspace_id=workspace_id,
            public_thread_id=threadId,
            public_job_id=jobId,
            is_final=isFinal,
            limit=limit,
            offset=offset,
        )
    except GenerationOutputPersistenceUnavailable as exc:
        raise_api_error(
            status_code=503,
            error_code="generation_output_storage_unavailable",
            message="Generation output storage is not available.",
            detail=str(exc),
        )
    empty_state = None
    if not items:
        empty_state = EmptyState(
            kind="no_generation_outputs",
            title="No outputs found.",
            message="No generation outputs match the criteria.",
        )
    return GenerationOutputListResponse(
        items=items,
        pagination=Pagination(limit=limit, offset=offset, total=total, has_more=(offset + len(items)) < total),
        empty_state=empty_state,
    )


@router.get("/generation-outputs/{output_id}", response_model=GenerationOutputResponse)
def get_generation_output_route(
    output_id: str,
    workspace_id: str | None = None,
    user_id: str | None = None,
) -> GenerationOutputResponse:
    from orchestrator.app.db.workspace_scope import resolve_workspace_scope, WorkspaceScopeForbidden, WorkspaceScopeRequired
    try:
        workspace_id = resolve_workspace_scope(workspace_id, user_id=user_id)
    except WorkspaceScopeForbidden as e:
        raise_api_error(403, "workspace_forbidden", "Workspace access denied.", detail=str(e))
    except WorkspaceScopeRequired as e:
        raise_api_error(400, "workspace_required", "Workspace is required.", detail=str(e))
    try:
        return get_generation_output(public_output_id=output_id, workspace_id=workspace_id)
    except GenerationOutputNotFound:
        raise_api_error(
            status_code=404,
            error_code="generation_output_not_found",
            message="Generation output was not found.",
            detail=f"output_id={output_id}",
        )
    except GenerationOutputPersistenceUnavailable as exc:
        raise_api_error(
            status_code=503,
            error_code="generation_output_storage_unavailable",
            message="Generation output storage is not available.",
            detail=str(exc),
        )


@router.post("/generation-outputs/{output_id}/select-final", response_model=GenerationOutputResponse)
def select_final_generation_output_route(
    output_id: str,
    workspace_id: str | None = None,
    user_id: str | None = None,
) -> GenerationOutputResponse:
    from orchestrator.app.db.workspace_scope import resolve_workspace_scope, WorkspaceScopeForbidden, WorkspaceScopeRequired
    try:
        workspace_id = resolve_workspace_scope(workspace_id, user_id=user_id)
    except WorkspaceScopeForbidden as e:
        raise_api_error(403, "workspace_forbidden", "Workspace access denied.", detail=str(e))
    except WorkspaceScopeRequired as e:
        raise_api_error(400, "workspace_required", "Workspace is required.", detail=str(e))
    try:
        return select_final_generation_output(public_output_id=output_id, workspace_id=workspace_id)
    except GenerationOutputNotFound:
        raise_api_error(
            status_code=404,
            error_code="generation_output_not_found",
            message="Generation output was not found.",
            detail=f"output_id={output_id}",
        )
    except GenerationOutputPersistenceUnavailable as exc:
        raise_api_error(
            status_code=503,
            error_code="generation_output_storage_unavailable",
            message="Generation output storage is not available.",
            detail=str(exc),
        )
