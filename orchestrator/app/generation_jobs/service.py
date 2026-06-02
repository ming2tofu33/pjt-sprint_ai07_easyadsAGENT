"""In-memory GenerationJob service skeleton."""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from uuid import uuid4

from orchestrator.app.api.schemas.generation_jobs import (
    GenerationJobCreateRequest,
    GenerationJobResponse,
    GenerationProgress,
)
from orchestrator.app.api.schemas.common import ErrorResponse
from orchestrator.app.db import settings as db_settings
from orchestrator.app.db.repositories import chat_threads as chat_thread_repo
from orchestrator.app.db.repositories import generation_jobs as generation_job_repo
from orchestrator.app.db.repositories import workspaces as workspace_repo
from orchestrator.app.db.session import db_transaction

_GENERATION_JOBS: dict[str, GenerationJobResponse] = {}
_BLOCKED_METADATA_KEYS = {
    "api_key",
    "openai_api_key",
    "hf_token",
    "huggingface_token",
    "token",
    "authorization",
    "password",
    "secret",
    "service_role_key",
}
_RESERVED_METADATA_KEYS = {
    "requested_run_mode",
    "effective_run_mode",
    "execution_mode",
    "user_input_preview",
}

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
    sanitized = _sanitize_metadata_value(metadata)
    if not isinstance(sanitized, dict):
        return {}
    return {
        key: value
        for key, value in sanitized.items()
        if str(key).lower() not in _RESERVED_METADATA_KEYS
    }


def _sanitize_metadata_value(value):
    if isinstance(value, dict):
        output = {}
        for key, item in value.items():
            normalized_key = str(key).lower()
            if normalized_key in _BLOCKED_METADATA_KEYS:
                continue
            if normalized_key in _RESERVED_METADATA_KEYS:
                continue
            output[key] = _sanitize_metadata_value(item)
        return output
    if isinstance(value, list):
        return [_sanitize_metadata_value(item) for item in value[:50]]
    if isinstance(value, str):
        if len(value) > 500:
            return f"{value[:497]}..."
        return value
    return value


def _initial_run_mode_metadata(run_mode: str) -> tuple[str, str]:
    if run_mode == "mock_immediate":
        return "mock_immediate", "pending_deterministic_mock"
    if run_mode == "graph_immediate":
        return "queued_only", "degraded_no_graph_execution"
    if run_mode in {"gpt_image_2_actual", "gpt_image_2_smoke"}:
        return "gpt_image_2_actual", "pending_t2i_actual"
    if run_mode in {"sd35_local", "sd35_local_smoke"}:
        return "sd35_local", "pending_t2i_actual"
    if run_mode in {"flux_local", "flux_local_smoke", "flux", "flux_smoke"}:
        return "flux_local", "pending_t2i_actual"
    return "queued_only", "queued_only"


def create_generation_job(request: GenerationJobCreateRequest) -> GenerationJobResponse:
    if _use_postgres_backend():
        return _create_generation_job_db(request)
    return _create_generation_job_memory(request)


def _create_generation_job_memory(request: GenerationJobCreateRequest) -> GenerationJobResponse:
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
            "engine_preference": _engine_preference(request.run_mode),
            "t2i_engine": _engine_preference(request.run_mode),
            **_safe_request_metadata(request.metadata),
        },
    )
    _GENERATION_JOBS[job.job_id] = job
    return job


def get_generation_job(job_id: str) -> GenerationJobResponse | None:
    if _use_postgres_backend():
        row = generation_job_repo.get_generation_job_row(job_id)
        return _job_response_from_db_row(row)
    return _GENERATION_JOBS.get(job_id)


def update_generation_job(job_id: str, **fields) -> GenerationJobResponse | None:
    if _use_postgres_backend():
        existing = get_generation_job(job_id)
        if not existing:
            return None
        row_fields = _db_update_fields(existing, fields)
        row = generation_job_repo.update_generation_job_row(job_id, **row_fields)
        return _job_response_from_db_row(row)

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


def _engine_preference(run_mode: str) -> str | None:
    if run_mode in {"gpt_image_2_actual", "gpt_image_2_smoke"}:
        return "gpt_image_2"
    if run_mode in {"sd35_local", "sd35_local_smoke"}:
        return "sd35_large"
    if run_mode in {"flux_local", "flux_local_smoke", "flux", "flux_smoke"}:
        return "flux"
    return None


def _use_postgres_backend() -> bool:
    return db_settings.get_db_backend() == "postgres"


def _create_generation_job_db(request: GenerationJobCreateRequest) -> GenerationJobResponse:
    now = _now_iso()
    effective_run_mode, execution_mode = _initial_run_mode_metadata(request.run_mode)
    user_id = request.user_id or db_settings.get_demo_user_id()
    public_job_id = f"job_{uuid4().hex}"
    prompt_preview = _preview_user_input(request.user_input)
    request_payload = _request_payload_summary(request)
    with db_transaction() as conn:
        workspace = workspace_repo.ensure_demo_workspace(user_id=user_id, connection=conn)
        thread = chat_thread_repo.create_chat_thread(
            workspace_id=str(workspace["id"]),
            created_by=user_id,
            title=_preview_user_input(request.user_input, max_length=80),
            brand_kit_id=request.brand_kit_id,
            connection=conn,
        )
        metadata = {
            "requested_run_mode": request.run_mode,
            "effective_run_mode": effective_run_mode,
            "execution_mode": execution_mode,
            "user_input_preview": prompt_preview,
            "brand_kit_id": request.brand_kit_id,
            "user_id": request.user_id,
            "entry_mode": request.entry_mode,
            "copy_generation_mode": request.copy_generation_mode,
            "user_plan": request.user_plan,
            "selected_reference_template_id": request.selected_reference_template_id,
            "ad_format": request.ad_format,
            "workspace_id": str(workspace["id"]),
            "public_thread_id": thread.get("public_thread_id"),
            "engine_preference": _engine_preference(request.run_mode),
            "t2i_engine": _engine_preference(request.run_mode),
            **_safe_request_metadata(request.metadata),
        }
        row = generation_job_repo.create_generation_job_row(
            public_job_id=public_job_id,
            workspace_id=str(workspace["id"]),
            thread_id=str(thread["id"]) if thread.get("id") else None,
            requested_by=user_id,
            status="queued",
            current_stage="queued",
            progress_percent=0,
            selected_reference_template_id=request.selected_reference_template_id,
            output_path=None,
            result_payload=None,
            error=None,
            metadata=metadata,
            run_mode=request.run_mode,
            engine=_engine_preference(request.run_mode),
            model_provider=_engine_preference(request.run_mode),
            prompt_hash=hashlib.sha256(request.user_input.encode("utf-8")).hexdigest(),
            prompt_preview=prompt_preview,
            request_payload=request_payload,
            connection=conn,
        )
    response = _job_response_from_db_row(row)
    if response:
        return response
    return GenerationJobResponse(
        job_id=public_job_id,
        thread_id=thread.get("public_thread_id"),
        user_id=request.user_id,
        brand_kit_id=request.brand_kit_id,
        status="queued",
        progress=GenerationProgress(progress_percent=0, current_stage="queued", stage_order=DEFAULT_STAGE_ORDER),
        selected_reference_template_id=request.selected_reference_template_id,
        output_path=None,
        result_payload=None,
        error=None,
        created_at=now,
        updated_at=now,
        metadata=metadata,
    )


def _db_update_fields(existing: GenerationJobResponse, fields: dict) -> dict:
    metadata = fields.get("metadata", existing.metadata)
    if fields.get("metadata") is not None:
        metadata = fields["metadata"]
    progress = fields.get("progress", existing.progress)
    error = fields.get("error", existing.error)
    return {
        "status": fields.get("status", existing.status),
        "current_stage": progress.current_stage,
        "progress_percent": progress.progress_percent,
        "output_path": fields.get("output_path", existing.output_path),
        "result_payload": fields.get("result_payload", existing.result_payload),
        "error": error.model_dump(mode="json") if hasattr(error, "model_dump") else error,
        "metadata": metadata,
    }


def _job_response_from_db_row(row: dict | None) -> GenerationJobResponse | None:
    if not row:
        return None
    metadata = row.get("metadata") or {}
    error = row.get("error")
    return GenerationJobResponse(
        job_id=str(row.get("public_job_id")),
        thread_id=metadata.get("public_thread_id") or _string_or_none(row.get("thread_id")),
        user_id=metadata.get("user_id"),
        brand_kit_id=metadata.get("brand_kit_id"),
        status=row.get("status") or "queued",
        progress=GenerationProgress(
            progress_percent=int(row.get("progress_percent") or 0),
            current_stage=str(row.get("current_stage") or "queued"),
            estimated_seconds_remaining=None,
            stage_order=DEFAULT_STAGE_ORDER,
        ),
        selected_reference_template_id=row.get("selected_reference_template_id"),
        output_path=row.get("output_path"),
        result_payload=row.get("result_payload"),
        error=ErrorResponse(**error) if isinstance(error, dict) else None,
        created_at=_iso(row.get("created_at")),
        updated_at=_iso(row.get("updated_at")),
        metadata=metadata,
    )


def _iso(value) -> str:
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return str(value or _now_iso())


def _string_or_none(value) -> str | None:
    return str(value) if value is not None else None


def _request_payload_summary(request: GenerationJobCreateRequest) -> dict:
    return {
        "entry_mode": request.entry_mode,
        "run_mode": request.run_mode,
        "ad_format": request.ad_format,
        "copy_generation_mode": request.copy_generation_mode,
        "selected_reference_template_id": request.selected_reference_template_id,
        "user_plan": request.user_plan,
        "user_input_preview": _preview_user_input(request.user_input),
        "metadata": _safe_request_metadata(request.metadata),
    }
