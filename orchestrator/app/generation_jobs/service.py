"""In-memory GenerationJob service skeleton."""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from orchestrator.app.api.schemas.generation_jobs import (
    GenerationJobCreateRequest,
    GenerationJobResponse,
    GenerationProgress,
)
from orchestrator.app.api.schemas.common import ErrorResponse

_GENERATION_JOBS: dict[str, GenerationJobResponse] = {}

DEFAULT_STAGE_ORDER = [
    "briefing",
    "planning",
    "t2i_running",
    "validating",
    "rendering",
    "completed",
]


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _preview_user_input(value: str, max_length: int = 120) -> str:
    normalized = " ".join(value.split())
    if len(normalized) <= max_length:
        return normalized
    return f"{normalized[: max_length - 3]}..."


def _safe_request_metadata(metadata: dict | None) -> dict:
    if not metadata:
        return {}
    blocked = {"api_key", "openai_api_key", "hf_token", "huggingface_token", "token"}
    reserved = {"requested_run_mode", "effective_run_mode", "execution_mode", "user_input_preview"}
    return {
        key: value
        for key, value in metadata.items()
        if key.lower() not in blocked and key not in reserved
    }


def _initial_run_mode_metadata(run_mode: str) -> tuple[str, str]:
    if run_mode == "mock_immediate":
        return "mock_immediate", "pending_deterministic_mock"
    if run_mode == "graph_immediate":
        return "queued_only", "degraded_no_graph_execution"
    if run_mode in {"gpt_image_2_actual", "gpt_image_2_smoke"}:
        return "gpt_image_2_actual", "pending_t2i_actual"
    if run_mode in {"sd35_local", "sd35_local_smoke"}:
        return "sd35_local", "pending_t2i_actual"
    return "queued_only", "queued_only"


def create_generation_job(request: GenerationJobCreateRequest) -> GenerationJobResponse:
    now = _now_iso()
    effective_run_mode, execution_mode = _initial_run_mode_metadata(request.run_mode)
    job = GenerationJobResponse(
        job_id=f"job_{uuid4().hex}",
        thread_id=f"thread_{uuid4().hex}",
        user_id=request.user_id,
        brand_kit_id=request.brand_kit_id,
        status="queued",
        progress=GenerationProgress(
            progress_percent=0,
            current_stage="queued",
            estimated_seconds_remaining=None,
            stage_order=DEFAULT_STAGE_ORDER,
        ),
        selected_reference_template_id=request.selected_reference_template_id,
        output_path=None,
        result_payload=None,
        error=None,
        created_at=now,
        updated_at=now,
        metadata={
            "requested_run_mode": request.run_mode,
            "effective_run_mode": effective_run_mode,
            "execution_mode": execution_mode,
            "user_input_preview": _preview_user_input(request.user_input),
            "brand_kit_id": request.brand_kit_id,
            "user_id": request.user_id,
            "entry_mode": request.entry_mode,
            "copy_generation_mode": request.copy_generation_mode,
            "user_plan": request.user_plan,
            "selected_reference_template_id": request.selected_reference_template_id,
            "ad_format": request.ad_format,
            **_safe_request_metadata(request.metadata),
        },
    )
    _GENERATION_JOBS[job.job_id] = job
    return job


def get_generation_job(job_id: str) -> GenerationJobResponse | None:
    return _GENERATION_JOBS.get(job_id)


def update_generation_job(job_id: str, **fields) -> GenerationJobResponse | None:
    existing = get_generation_job(job_id)
    if not existing:
        return None
    updated = existing.model_copy(update={**fields, "updated_at": _now_iso()})
    _GENERATION_JOBS[job_id] = updated
    return updated


def mark_generation_job_running(job_id: str, stage: str = "running") -> GenerationJobResponse | None:
    existing = get_generation_job(job_id)
    if not existing:
        return None
    progress = existing.progress.model_copy(update={"progress_percent": 50, "current_stage": stage})
    return update_generation_job(job_id, status="running", progress=progress)


def mark_generation_job_done(
    job_id: str,
    result_payload: dict,
    output_path: str | None = None,
    metadata: dict | None = None,
) -> GenerationJobResponse | None:
    existing = get_generation_job(job_id)
    if not existing:
        return None
    progress = existing.progress.model_copy(update={"progress_percent": 100, "current_stage": "completed"})
    merged_metadata = {**existing.metadata, **(metadata or {})}
    return update_generation_job(
        job_id,
        status="done",
        progress=progress,
        output_path=output_path,
        result_payload=result_payload,
        error=None,
        metadata=merged_metadata,
    )


def mark_generation_job_failed(job_id: str, error: dict, metadata: dict | None = None) -> GenerationJobResponse | None:
    existing = get_generation_job(job_id)
    if not existing:
        return None
    merged_metadata = {**existing.metadata, **(metadata or {})}
    progress = existing.progress.model_copy(update={"current_stage": "failed"})
    return update_generation_job(
        job_id,
        status="failed",
        progress=progress,
        error=ErrorResponse(
            error_code=str(error.get("error_code") or "generation_job_execution_failed"),
            message=str(error.get("message") or "Generation job execution failed."),
            detail=error.get("detail"),
        ),
        metadata=merged_metadata,
    )


def reset_generation_job_store_for_tests() -> None:
    _GENERATION_JOBS.clear()
