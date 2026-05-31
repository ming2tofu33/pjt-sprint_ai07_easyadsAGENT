"""In-memory GenerationJob service skeleton."""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from orchestrator.app.api.schemas.generation_jobs import (
    GenerationJobCreateRequest,
    GenerationJobResponse,
    GenerationProgress,
)

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


def create_generation_job(request: GenerationJobCreateRequest) -> GenerationJobResponse:
    now = _now_iso()
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
            "effective_run_mode": "queued_only",
            "user_input_preview": _preview_user_input(request.user_input),
            "brand_kit_id": request.brand_kit_id,
            "user_id": request.user_id,
            "entry_mode": request.entry_mode,
            "copy_generation_mode": request.copy_generation_mode,
            "user_plan": request.user_plan,
            "selected_reference_template_id": request.selected_reference_template_id,
            "ad_format": request.ad_format,
        },
    )
    _GENERATION_JOBS[job.job_id] = job
    return job


def get_generation_job(job_id: str) -> GenerationJobResponse | None:
    return _GENERATION_JOBS.get(job_id)


def reset_generation_job_store_for_tests() -> None:
    _GENERATION_JOBS.clear()
