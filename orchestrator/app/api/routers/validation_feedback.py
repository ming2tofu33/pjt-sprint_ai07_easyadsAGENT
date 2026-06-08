"""Validation feedback and regeneration API routes."""

from __future__ import annotations

from fastapi import APIRouter, Response

from orchestrator.app.api.errors import raise_api_error
from orchestrator.app.api.schemas.validation_feedback import (
    RegenerateOutputRequest,
    RegenerateOutputResponse,
    ValidationDetailResponse,
)
from orchestrator.app.db.workspace_scope import WorkspaceScopeForbidden, WorkspaceScopeRequired, resolve_workspace_scope
from orchestrator.app.validation_feedback.errors import ValidationFeedbackError
from orchestrator.app.validation_feedback.service import create_validation_report_for_output, get_latest_validation_for_output, regenerate_output

router = APIRouter()


@router.get("/generation-outputs/{output_id}/validation", response_model=ValidationDetailResponse)
def get_generation_output_validation_route(
    output_id: str,
    workspace_id: str | None = None,
    user_id: str | None = None,
) -> ValidationDetailResponse:
    workspace_id = _resolve_workspace(workspace_id, user_id)
    try:
        validation = get_latest_validation_for_output(public_output_id=output_id, workspace_id=workspace_id)
    except ValidationFeedbackError as exc:
        raise_api_error(exc.status_code, exc.error_code, exc.message)
    return ValidationDetailResponse(validation=validation)


@router.post("/generation-outputs/{output_id}/validation", response_model=ValidationDetailResponse)
def create_generation_output_validation_route(
    output_id: str,
    workspace_id: str | None = None,
    user_id: str | None = None,
) -> ValidationDetailResponse:
    workspace_id = _resolve_workspace(workspace_id, user_id)
    try:
        validation = create_validation_report_for_output(public_output_id=output_id, workspace_id=workspace_id, created_by=user_id)
    except ValidationFeedbackError as exc:
        raise_api_error(exc.status_code, exc.error_code, exc.message)
    return ValidationDetailResponse(validation=validation)


@router.post("/generation-outputs/{output_id}/regenerate", response_model=RegenerateOutputResponse)
def regenerate_generation_output_route(
    output_id: str,
    request: RegenerateOutputRequest,
    response: Response,
    workspace_id: str | None = None,
    user_id: str | None = None,
) -> RegenerateOutputResponse:
    workspace_id = _resolve_workspace(workspace_id, user_id)
    try:
        status_code, regeneration = regenerate_output(
            public_output_id=output_id,
            workspace_id=workspace_id,
            suggested_actions=request.suggested_actions,
            scope=request.scope,
            user_instruction=request.user_instruction,
            idempotency_key=request.idempotency_key,
        )
    except ValidationFeedbackError as exc:
        raise_api_error(exc.status_code, exc.error_code, exc.message)
    response.status_code = status_code
    return RegenerateOutputResponse(regeneration=regeneration)


def _resolve_workspace(workspace_id: str | None, user_id: str | None) -> str:
    try:
        return resolve_workspace_scope(workspace_id, user_id=user_id)
    except WorkspaceScopeForbidden as exc:
        raise_api_error(403, "workspace_forbidden", "Workspace access denied.", detail=str(exc))
    except WorkspaceScopeRequired as exc:
        raise_api_error(400, "workspace_required", "Workspace is required.", detail=str(exc))
