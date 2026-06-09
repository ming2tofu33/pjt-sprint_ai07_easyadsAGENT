"""GenerationJob API routes."""

from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, status

from orchestrator.app.api.errors import raise_api_error
from orchestrator.app.api.schemas.generation_jobs import (
    GenerationJobAnswerRequest,
    GenerationJobCreateRequest,
    GenerationJobCreateResponse,
    GenerationJobGetResponse,
)
from orchestrator.app.generation_jobs.execution import (
    execute_generation_job_immediate,
    execute_generation_job_t2i,
    execute_generation_job_graph,
    resume_generation_job_graph,
)
from orchestrator.app.generation_jobs.service import (
    create_generation_job,
    get_generation_job,
    mark_generation_job_running,
    maybe_mark_stale_generation_job_failed,
    maybe_poll_generation_job_from_modal,
    maybe_submit_generation_job_to_modal,
    should_route_generation_job_to_modal,
)
from orchestrator.app.chat_threads.errors import ChatThreadServiceError
from orchestrator.app.reference_catalog.service import get_reference_template

router = APIRouter()


def _generation_job_not_found(job_id: str) -> None:
    raise_api_error(
        status_code=404,
        error_code="generation_job_not_found",
        message="Generation job was not found.",
        detail=f"job_id={job_id}",
    )


def _reference_template_not_found(template_id: str) -> None:
    raise_api_error(
        status_code=404,
        error_code="reference_template_not_found",
        message="Reference template was not found.",
        detail=f"template_id={template_id}",
    )


def _chat_thread_error(exc: ChatThreadServiceError) -> None:
    if exc.error_code == "chat_thread_not_found":
        status_code = 404
    elif exc.error_code in {"chat_thread_archived", "chat_thread_has_active_job"}:
        status_code = 409
    else:
        status_code = 400
    raise_api_error(
        status_code=status_code,
        error_code=exc.error_code,
        message=exc.message,
    )


@router.post("/generation-jobs", response_model=GenerationJobCreateResponse, status_code=status.HTTP_201_CREATED)
def create_generation_job_route(
    request: GenerationJobCreateRequest,
    background_tasks: BackgroundTasks,
) -> GenerationJobCreateResponse:
    if request.selected_reference_template_id and not get_reference_template(request.selected_reference_template_id):
        _reference_template_not_found(request.selected_reference_template_id)
    from orchestrator.app.generation_jobs.errors import GenerationJobError
    try:
        job = create_generation_job(request)
    except ChatThreadServiceError as exc:
        _chat_thread_error(exc)
    except GenerationJobError as exc:
        raise_api_error(
            status_code=exc.status_code,
            error_code=exc.error_code,
            message=exc.message,
        )
    if should_route_generation_job_to_modal(request):
        job = maybe_submit_generation_job_to_modal(job, request)
    elif request.run_mode == "mock_immediate":
        job = execute_generation_job_immediate(job.job_id, request)
    elif request.run_mode == "graph_job":
        background_tasks.add_task(execute_generation_job_graph, job.job_id, request)
    elif request.run_mode in {"gpt_image_1_actual", "gpt_image_1_smoke"}:
        job = execute_generation_job_t2i(job.job_id, request, engine_name="gpt_image_1")
    elif request.run_mode in {"gpt_image_2_actual", "gpt_image_2_smoke"}:
        job = execute_generation_job_t2i(job.job_id, request, engine_name="gpt_image_2")
    elif request.run_mode in {"sd35_local", "sd35_local_smoke", "sd35_large_real"}:
        job = execute_generation_job_t2i(job.job_id, request, engine_name="sd35_large")
    elif request.run_mode in {"flux_local", "flux_local_smoke", "flux_schnell_real", "flux", "flux_smoke"}:
        job = execute_generation_job_t2i(job.job_id, request, engine_name="flux")
    return GenerationJobCreateResponse(job=job)


@router.get("/generation-jobs/{job_id}", response_model=GenerationJobGetResponse)
def get_generation_job_route(
    job_id: str,
    workspace_id: str | None = None,
    user_id: str | None = None,
) -> GenerationJobGetResponse:
    from orchestrator.app.generation_jobs.errors import GenerationJobError
    try:
        job = get_generation_job(job_id, workspace_id=workspace_id, user_id=user_id)
    except GenerationJobError as exc:
        raise_api_error(status_code=exc.status_code, error_code=exc.error_code, message=exc.message)
    if not job:
        _generation_job_not_found(job_id)
    job = maybe_mark_stale_generation_job_failed(job)
    if job.status != "failed":
        job = maybe_poll_generation_job_from_modal(job)
    return GenerationJobGetResponse(job=job)


@router.post("/generation-jobs/{job_id}/answer", response_model=GenerationJobGetResponse)
def answer_generation_job_route(
    job_id: str,
    request: GenerationJobAnswerRequest,
    background_tasks: BackgroundTasks,
    workspace_id: str | None = None,
    user_id: str | None = None,
) -> GenerationJobGetResponse:
    from orchestrator.app.generation_jobs.errors import GenerationJobError
    try:
        job = get_generation_job(job_id, workspace_id=workspace_id, user_id=user_id)
    except GenerationJobError as exc:
        raise_api_error(status_code=exc.status_code, error_code=exc.error_code, message=exc.message)
    if not job:
        _generation_job_not_found(job_id)
    if job.status != "waiting_user_input":
        raise_api_error(
            status_code=409,
            error_code="generation_job_resume_failed",
            message="Generation job could not be resumed.",
            detail="generation job is not waiting for user input",
        )
    if not job.thread_id:
        raise_api_error(
            status_code=409,
            error_code="generation_job_resume_failed",
            message="Generation job could not be resumed.",
            detail="generation job has no thread_id",
        )
    try:
        running = mark_generation_job_running(job_id, stage="planning")
        background_tasks.add_task(resume_generation_job_graph, job_id, request, allow_running=True)
    except ValueError as exc:
        raise_api_error(
            status_code=409,
            error_code="generation_job_resume_failed",
            message="Generation job could not be resumed.",
            detail=str(exc),
        )
    return GenerationJobGetResponse(job=running or job)
