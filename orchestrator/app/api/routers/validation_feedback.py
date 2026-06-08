"""Validation feedback and regeneration API routes."""

from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, Response

from orchestrator.app.api.errors import raise_api_error
from orchestrator.app.api.schemas.validation_feedback import (
    RegenerateOutputRequest,
    RegenerateOutputResponse,
    ValidationDetailResponse,
)
from orchestrator.app.db.workspace_scope import WorkspaceScopeForbidden, WorkspaceScopeRequired, resolve_workspace_scope
from orchestrator.app.validation_feedback.errors import ValidationFeedbackError
from orchestrator.app.validation_feedback.service import create_validation_report_for_output, get_latest_validation_for_output, regenerate_output
from orchestrator.app.api.schemas.generation_jobs import GenerationJobCreateRequest
from orchestrator.app.generation_jobs.execution import execute_generation_job_graph, execute_generation_job_immediate, execute_generation_job_t2i

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
    background_tasks: BackgroundTasks,
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
            requested_by=user_id,
        )
    except ValidationFeedbackError as exc:
        raise_api_error(exc.status_code, exc.error_code, exc.message)
    dispatch = regeneration.pop("_dispatch", None)
    if status_code == 202 and dispatch:
        _dispatch_regeneration_job(background_tasks, dispatch)
    response.status_code = status_code
    return RegenerateOutputResponse(regeneration=regeneration)


def _resolve_workspace(workspace_id: str | None, user_id: str | None) -> str:
    try:
        return resolve_workspace_scope(workspace_id, user_id=user_id)
    except WorkspaceScopeForbidden as exc:
        raise_api_error(403, "workspace_forbidden", "Workspace access denied.", detail=str(exc))
    except WorkspaceScopeRequired as exc:
        raise_api_error(400, "workspace_required", "Workspace is required.", detail=str(exc))


def _dispatch_regeneration_job(background_tasks: BackgroundTasks, dispatch: dict) -> None:
    job_id = dispatch.get("jobId")
    request_payload = dispatch.get("request") or {}
    if not job_id:
        return
    request = GenerationJobCreateRequest(**request_payload)
    run_mode = request.run_mode
    if run_mode == "mock_immediate":
        background_tasks.add_task(execute_generation_job_immediate, job_id, request)
    elif run_mode == "graph_job":
        background_tasks.add_task(execute_generation_job_graph, job_id, request)
    elif run_mode in {"gpt_image_1_actual", "gpt_image_1_smoke"}:
        background_tasks.add_task(execute_generation_job_t2i, job_id, request, "gpt_image_1")
    elif run_mode in {"gpt_image_2_actual", "gpt_image_2_smoke"}:
        background_tasks.add_task(execute_generation_job_t2i, job_id, request, "gpt_image_2")
    elif run_mode in {"sd35_local", "sd35_local_smoke", "sd35_large_real"}:
        background_tasks.add_task(execute_generation_job_t2i, job_id, request, "sd35_large")
    elif run_mode in {"flux_local", "flux_local_smoke", "flux_schnell_real", "flux", "flux_smoke"}:
        background_tasks.add_task(execute_generation_job_t2i, job_id, request, "flux")
