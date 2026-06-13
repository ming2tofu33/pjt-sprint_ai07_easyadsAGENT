"""In-memory GenerationJob service skeleton."""

from __future__ import annotations

import hashlib
import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path
from threading import RLock
from uuid import UUID
from uuid import uuid4

from orchestrator.app.api.schemas.chat_threads import ChatMessageCreateRequest
from orchestrator.app.api.schemas.generation_jobs import (
    GenerationJobAnswerRequest,
    GenerationJobCreateRequest,
    GenerationJobResponse,
    GenerationProgress,
)
from orchestrator.app.api.schemas.common import ErrorResponse
from orchestrator.app.artifacts.service import (
    merge_final_asset_into_result_payload,
    normalize_repo_relative_artifact_path,
    sanitize_result_artifact_payload_for_api,
)
from orchestrator.app.db import settings as db_settings
from orchestrator.app.db.repositories import assets as asset_repo
from orchestrator.app.db.repositories import chat_messages as chat_message_repo
from orchestrator.app.db.repositories import chat_threads as chat_thread_repo
from orchestrator.app.db.repositories import generation_job_events as generation_job_event_repo
from orchestrator.app.db.repositories import generation_jobs as generation_job_repo
from orchestrator.app.db.repositories import generation_outputs as generation_output_repo
from orchestrator.app.db.repositories import workspaces as workspace_repo
from orchestrator.app.db.session import db_transaction
from orchestrator.app.chat_threads.errors import (
    ChatThreadArchivedError,
    ChatThreadHasActiveJobError,
    ChatThreadNotFoundError,
)
from orchestrator.app.generation_jobs.errors import (
    GenerationJobAuthenticationRequired,
    GenerationJobInvalidWorkspaceId,
    GenerationJobWorkspaceForbidden,
    GenerationJobWorkspaceNotFound,
    GenerationJobWorkspaceRequired,
)
from orchestrator.app.chat_threads import service as chat_thread_service
from orchestrator.app.chat_threads.sanitization import sanitize_chat_payload
from orchestrator.app.chat_threads import state_service
from orchestrator.app.chat_threads.state_snapshot import calculate_changed_fields
from orchestrator.app.modal import settings as modal_settings
from orchestrator.app.modal.errors import ModalExecutionError, ModalJobPollError
from orchestrator.app.modal.service import (
    build_modal_t2i_request_from_job,
    is_modal_eligible_run_mode,
    poll_and_process_modal_generation_job,
    submit_generation_job_to_modal,
)
from orchestrator.app.storage import settings as storage_settings
from orchestrator.app.storage.errors import AssetStorageError
from orchestrator.app.storage.object_keys import build_generation_object_key
from orchestrator.app.storage.r2_service import upload_file_to_r2
from orchestrator.app.usage import service as usage_service
from orchestrator.app.archive import service as archive_service


logger = logging.getLogger(__name__)

_GENERATION_JOBS: dict[str, GenerationJobResponse] = {}
_GENERATION_JOB_WORKSPACES: dict[str, str] = {}
_GENERATION_JOB_LOCK = RLock()
STALE_RUNNING_STAGE_NAMES = {"planning", "running"}
DEFAULT_STALE_RUNNING_AFTER_SECONDS = 15 * 60
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
    "account_type",
    "user_input_preview",
}
PUBLIC_METADATA_BLOCKED_KEYS = {
    "workspace_id",
    "internal_job_id",
    "internal_thread_id",
    "input_asset_uuid",
    "reference_asset_uuid",
    "bucket",
    "object_key",
    "modal_call_id",
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
    if run_mode == "graph_job":
        return "graph_job", "pending_graph_execution"
    if run_mode in {"gpt_image_1_actual", "gpt_image_1_smoke"}:
        return "gpt_image_1_actual", "pending_t2i_actual"
    if run_mode in {"gpt_image_2_actual", "gpt_image_2_smoke"}:
        return "gpt_image_2_actual", "pending_t2i_actual"
    if run_mode in {"sd35_local", "sd35_local_smoke", "sd35_large_real"}:
        return "sd35_local", "pending_t2i_actual"
    if run_mode in {"flux_local", "flux_local_smoke", "flux_schnell_real", "flux", "flux_smoke", "flux2_klein_4b"}:
        return "flux_local", "pending_t2i_actual"
    return "queued_only", "queued_only"


def create_generation_job(request: GenerationJobCreateRequest) -> GenerationJobResponse:
    if _use_postgres_backend():
        return _create_generation_job_db(request)
    return _create_generation_job_memory(request)


def _answer_display_text(answer: GenerationJobAnswerRequest) -> str:
    for value in (
        answer.display_text,
        answer.custom_text,
        answer.user_custom_headline,
        answer.selected_copy_id,
        answer.value,
    ):
        if value and str(value).strip():
            return str(value).strip()
    return ""


def _answer_message_payload(answer: GenerationJobAnswerRequest) -> dict:
    payload = answer.to_resume_payload(job_id="", thread_id="")
    payload.pop("job_id", None)
    payload.pop("thread_id", None)
    return {
        "source": "generation_job_answer",
        "field": answer.field,
        "value": answer.value,
        "display_text": answer.display_text,
        "answer": _sanitize_metadata_value(payload),
    }


def append_generation_job_user_answer_message(
    job_id: str,
    answer: GenerationJobAnswerRequest,
    *,
    workspace_id: str | None = None,
    user_id: str | None = None,
) -> None:
    content = _answer_display_text(answer)
    if not content:
        return
    if _use_postgres_backend():
        _append_generation_job_user_answer_message_db(job_id, answer, content, workspace_id=workspace_id, user_id=user_id)
        return

    job = get_generation_job(job_id, workspace_id=workspace_id, user_id=user_id) if workspace_id or user_id else get_generation_job_internal(job_id)
    if not job or not job.thread_id:
        return
    chat_thread_service.append_chat_message(
        job.thread_id,
        ChatMessageCreateRequest(
            role="user",
            content=content,
            payload={
                **_answer_message_payload(answer),
                "job_id": job_id,
            },
        ),
        user_id=job.user_id,
    )


def _create_generation_job_memory(request: GenerationJobCreateRequest) -> GenerationJobResponse:
    with _GENERATION_JOB_LOCK:
        now = _now_iso()
        workspace_id = request.workspace_id or "mem_workspace"
        if request.source_asset_id or request.reference_asset_id:
            from orchestrator.app.generation_jobs.errors import GenerationJobAssetPersistenceRequired
            raise GenerationJobAssetPersistenceRequired("Uploaded asset inputs require postgres persistence.")
        effective_run_mode, execution_mode = _initial_run_mode_metadata(request.run_mode)
        engine_preference = _engine_preference_for_request(request)

        if request.thread_id:
            existing_thread = chat_thread_service.get_chat_thread(request.thread_id, user_id=request.user_id)
            if not existing_thread:
                raise ChatThreadNotFoundError()
            if existing_thread.archived_at:
                raise ChatThreadArchivedError()
            if existing_thread.active_job_id:
                raise ChatThreadHasActiveJobError()
            public_thread_id = existing_thread.thread_id
        else:
            from orchestrator.app.api.schemas.chat_threads import ChatThreadCreateRequest
            new_thread = chat_thread_service.create_chat_thread(
                ChatThreadCreateRequest(
                    user_id=request.user_id,
                    title=_preview_user_input(request.user_input, max_length=80),
                    brand_kit_id=request.brand_kit_id,
                )
            )
            public_thread_id = new_thread.thread_id

        job = GenerationJobResponse(
            job_id=f"job_{uuid4().hex}",
            thread_id=public_thread_id,
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
            source_asset_id=request.source_asset_id,
            reference_asset_id=request.reference_asset_id,
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
                "engine_preference": engine_preference,
                "t2i_engine": engine_preference,
                **_safe_request_metadata(request.metadata),
            },
        )

        try:
            chat_thread_service.set_thread_active_job(public_thread_id, job.job_id, job.job_id, status="generating")
        except Exception:
            _GENERATION_JOBS.pop(job.job_id, None)
            raise

        # Parity: user_input message
        user_message = chat_thread_service.append_generation_job_chat_event_memory(
            thread_id=public_thread_id,
            job_id=job.job_id,
            event_type="user_input",
            role="user",
            content=request.user_input,
            payload={"source": "generation_job_input"},
            user_id=request.user_id,
        )

        # Snapshot parity
        latest_snapshot = state_service.get_latest_thread_state_for_user(
            public_thread_id=public_thread_id,
            user_id=request.user_id,
        )

        explicit_fields = {}
        for k in request.model_fields_set:
            if k in [
                "ad_format",
                "copy_generation_mode",
                "selected_reference_template_id",
                "source_image_path",
                "reference_image_path",
                "source_asset_id",
                "reference_asset_id",
                "selected_copy_id",
                "selected_channel_id",
                "selected_tone",
                "custom_direction",
                "user_custom_headline",
                "user_custom_subcopy",
                "brand_kit_id",
                "user_plan",
            ]:
                explicit_fields[k] = getattr(request, k)

        restored_payload = state_service.restore_thread_state(
            latest_snapshot,
            current_request_fields=explicit_fields,
            user_input=request.user_input,
        )
        _apply_generation_engine_to_state(restored_payload, request)
        changed_fields = calculate_changed_fields(
            latest_snapshot.state_payload if latest_snapshot else None,
            restored_payload
        )

        from orchestrator.app.reference_catalog.service import get_reference_template
        from orchestrator.app.brand_kits.service import get_brand_kit

        def _build_ref_snapshot(tid: str | None):
            if not tid: return {}
            t = get_reference_template(tid)
            if not t: return {}
            d = t.model_dump(mode="json")
            return {
                "template_id": d.get("template_id"),
                "category": d.get("category"),
                "business_type": d.get("business_types", d.get("business_type")),
                "style_keywords": d.get("style_keywords"),
                "color_palette": d.get("color_palette"),
                "composition": d.get("composition"),
                "reserved_text_areas": d.get("reserved_text_areas"),
                "aspect_ratio": d.get("aspect_ratio"),
            }

        def _build_brand_snapshot(bid: str | None):
            if not bid: return {}
            b = get_brand_kit(bid)
            if not b: return {}
            d = b.model_dump(mode="json")
            return {
                "brand_kit_id": d.get("brand_kit_id"),
                "brand_name": d.get("brand_name"),
                "primary_color": d.get("primary_color"),
                "secondary_color": d.get("secondary_color"),
                "fonts": d.get("fonts"),
            }

        # Use restored effective IDs if request didn't explicitly override
        effective_reference_id = restored_payload.get("selected_reference_template_id")
        effective_brand_kit_id = restored_payload.get("brand_kit_id")

        ref_snap = _build_ref_snapshot(effective_reference_id)
        brand_snap = _build_brand_snapshot(effective_brand_kit_id)

        snapshot_kind = "restored_input" if latest_snapshot else "input"
        state_service.save_thread_state_snapshot(
            public_thread_id=public_thread_id,
            workspace_id=workspace_id,
            snapshot_kind=snapshot_kind,
            state_payload=restored_payload,
            changed_fields=changed_fields,
            generation_job_id=job.job_id,
            source_message_id=user_message.message_id if user_message else None,
            parent_snapshot_id=latest_snapshot.snapshot_id if latest_snapshot else None,
            selected_reference_template_id=effective_reference_id,
            reference_template_snapshot=ref_snap,
            brand_kit_snapshot=brand_snap,
            snapshot_key=f"{job.job_id}:input",
            created_by=request.user_id,
            user_id=request.user_id,
        )

        # Queued event
        chat_thread_service.append_generation_job_chat_event_memory(
            thread_id=public_thread_id,
            job_id=job.job_id,
            event_type="generation_queued",
            role="system",
            content=None,
            payload={"job_id": job.job_id, "status": "queued"},
            user_id=request.user_id,
        )

        _GENERATION_JOBS[job.job_id] = job
        _GENERATION_JOB_WORKSPACES[job.job_id] = workspace_id
        return job


def get_generation_job(job_id: str, *, workspace_id: str | None = None, user_id: str | None = None) -> GenerationJobResponse | None:
    if workspace_id is not None or user_id is not None:
        return get_generation_job_scoped(job_id, workspace_id=workspace_id, user_id=user_id)
    return get_generation_job_internal(job_id)


def get_generation_job_scoped(job_id: str, *, workspace_id: str | None, user_id: str | None) -> GenerationJobResponse | None:
    if not workspace_id:
        raise GenerationJobWorkspaceRequired("workspaceId is required.")
    if not user_id and _use_postgres_backend() and not db_settings.allow_demo_workspace_fallback():
        raise GenerationJobAuthenticationRequired("Authenticated user is required.")
    if _use_postgres_backend():
        return _get_generation_job_db(job_id, workspace_id=workspace_id, user_id=user_id)
    with _GENERATION_JOB_LOCK:
        job = _GENERATION_JOBS.get(job_id)
        if job and _memory_job_workspace_id(job) != workspace_id:
            return None
        if job and user_id and job.user_id and job.user_id != user_id:
            return None
        return job


def get_generation_job_internal(job_id: str) -> GenerationJobResponse | None:
    if _use_postgres_backend():
        row = generation_job_repo.get_generation_job_internal_by_public_id(job_id)
        return _job_response_from_db_row(row)
    with _GENERATION_JOB_LOCK:
        return _GENERATION_JOBS.get(job_id)


def get_generation_job_internal_with_scope(job_id: str) -> tuple[GenerationJobResponse | None, str | None, str | None]:
    """Fetch a public job and the scope carried by the same DB row.

    Polling endpoints often receive only a public job id and the authenticated
    user. Returning the job plus its workspace/user scope avoids a second
    public_job_id lookup on every polling request.
    """
    if _use_postgres_backend():
        row = generation_job_repo.get_generation_job_internal_by_public_id(job_id)
        if not row:
            return None, None, None
        metadata = row.get("metadata") or {}
        workspace_id = str(row.get("workspace_id")) if row.get("workspace_id") else None
        user_id = (
            str(row.get("requested_by") or metadata.get("user_id"))
            if row.get("requested_by") or metadata.get("user_id")
            else None
        )
        return _job_response_from_db_row(row), workspace_id, user_id
    with _GENERATION_JOB_LOCK:
        job = _GENERATION_JOBS.get(job_id)
    if not job:
        return None, None, None
    return job, _memory_job_workspace_id(job), job.user_id


def resolve_generation_job_scope_from_existing_job(job_id: str) -> tuple[str | None, str | None]:
    if _use_postgres_backend():
        row = generation_job_repo.get_generation_job_internal_by_public_id(job_id)
        if not row:
            return None, None
        metadata = row.get("metadata") or {}
        return str(row.get("workspace_id")) if row.get("workspace_id") else None, (
            str(row.get("requested_by") or metadata.get("user_id"))
            if row.get("requested_by") or metadata.get("user_id")
            else None
        )
    with _GENERATION_JOB_LOCK:
        job = _GENERATION_JOBS.get(job_id)
    if not job:
        return None, None
    return _memory_job_workspace_id(job), job.user_id


def update_generation_job(job_id: str, *, workspace_id: str | None = None, user_id: str | None = None, **fields) -> GenerationJobResponse | None:
    if _use_postgres_backend():
        return _update_generation_job_db(job_id, workspace_id=workspace_id, user_id=user_id, **fields)

    existing = get_generation_job(job_id, workspace_id=workspace_id, user_id=user_id)
    if not existing:
        return None
    updated = existing.model_copy(update={**fields, "updated_at": _now_iso()})
    with _GENERATION_JOB_LOCK:
        _GENERATION_JOBS[job_id] = updated
    return updated


def mark_generation_job_running(job_id: str, stage: str = "running", *, workspace_id: str | None = None, user_id: str | None = None) -> GenerationJobResponse | None:
    if _use_postgres_backend():
        return _mark_generation_job_running_db(job_id, stage, workspace_id=workspace_id, user_id=user_id)
    existing = get_generation_job(job_id, workspace_id=workspace_id, user_id=user_id) if workspace_id or user_id else get_generation_job_internal(job_id)
    if not existing:
        return None
    progress = existing.progress.model_copy(update={"progress_percent": 50, "current_stage": stage})
    metadata = _without_pending_interrupt(existing.metadata or {})
    return update_generation_job(job_id, status="running", progress=progress, metadata=metadata)


def mark_generation_job_modal_running(
    job_id: str,
    *,
    modal_call_id: str,
    result_state: dict | None = None,
    metadata: dict | None = None,
) -> GenerationJobResponse | None:
    """Persist a graph Modal handoff without marking the job failed or done."""
    state_metadata = (result_state or {}).get("t2i_result", {}).get("metadata", {}) if isinstance(result_state, dict) else {}
    merged_metadata = {
        "execution_backend": "modal",
        "execution_mode": "graph_modal_pending",
        "graph_modal_pending": True,
        "modal_call_id_present": True,
        "modal_provider": "modal",
        "modal_status": "submitted",
        "graph_modal_snapshot_key": f"{job_id}:graph_modal_pending",
        "t2i_engine": state_metadata.get("requested_engine") or state_metadata.get("effective_engine") or state_metadata.get("engine"),
        **(metadata or {}),
    }
    if _use_postgres_backend():
        with db_transaction() as conn:
            row = generation_job_repo.get_generation_job_row(job_id, connection=conn)
            if not row:
                return None
            row_metadata = _without_pending_interrupt({**(row.get("metadata") or {}), **merged_metadata})
            row = generation_job_repo.update_generation_job_row(
                job_id,
                status="running",
                current_stage="modal_running",
                progress_percent=65,
                modal_call_id=modal_call_id,
                metadata=row_metadata,
                connection=conn,
            )
            if not row:
                return None
            _record_generation_job_event_db(
                row,
                "modal_submitted",
                payload={"modal_call_id_present": True, "source": "graph_t2i_generation"},
                connection=conn,
            )
        return _job_response_from_db_row(row)

    existing = get_generation_job(job_id)
    if not existing:
        return None
    progress = existing.progress.model_copy(update={"progress_percent": 65, "current_stage": "modal_running"})
    return update_generation_job(
        job_id,
        status="running",
        progress=progress,
        metadata=_without_pending_interrupt(
            {
                **(existing.metadata or {}),
                **merged_metadata,
                "modal_call_id": modal_call_id,
            }
        ),
    )


def mark_generation_job_done(
    job_id: str,
    result_payload: dict,
    output_path: str | None = None,
    metadata: dict | None = None,
    *,
    workspace_id: str | None = None,
    user_id: str | None = None,
) -> GenerationJobResponse | None:
    if _use_postgres_backend():
        return _mark_generation_job_done_db(job_id, result_payload, output_path=output_path, metadata=metadata, workspace_id=workspace_id, user_id=user_id)
    existing = get_generation_job(job_id, workspace_id=workspace_id, user_id=user_id) if workspace_id or user_id else get_generation_job_internal(job_id)
    if not existing:
        return None
    progress = existing.progress.model_copy(update={"progress_percent": 100, "current_stage": "completed"})
    merged_metadata = _without_pending_interrupt({**existing.metadata, **(metadata or {})})
    updated = update_generation_job(
        job_id,
        status="done",
        progress=progress,
        output_path=output_path,
        result_payload=result_payload,
        error=None,
        metadata=merged_metadata,
    )
    if updated and existing.thread_id:
        has_output = bool(output_path or (result_payload or {}).get("final_image_path") or (result_payload or {}).get("final_image_url") or (result_payload or {}).get("final_asset_id"))
        if has_output:
            chat_thread_service.set_thread_final_output(
                existing.thread_id,
                internal_output_id="memory_final_output",
                final_brief=(result_payload or {}).get("final_brief") or merged_metadata.get("final_brief"),
                expected_public_job_id=job_id,
            )
        transitioned = chat_thread_service.clear_thread_active_job(existing.thread_id, status="completed", expected_public_job_id=job_id)
        if not transitioned:
            return updated

        # completion event
        chat_thread_service.append_generation_job_chat_event_memory(
            thread_id=existing.thread_id,
            job_id=job_id,
            event_type="generation_completed",
            role="system",
            content="Generation completed.",
            payload={"job_id": job_id, "has_output": True},
            user_id=existing.user_id,
        )

        # completed snapshot
        latest_snapshot = state_service.get_latest_thread_state_for_user(
            public_thread_id=existing.thread_id,
            user_id=existing.user_id,
        )
        state_service.save_thread_state_snapshot(
            public_thread_id=existing.thread_id,
            workspace_id="mem_workspace",
            snapshot_kind="job_completed",
            state_payload=latest_snapshot.state_payload if latest_snapshot else {},
            changed_fields=[],
            generation_job_id=job_id,
            source_message_id=None,
            parent_snapshot_id=latest_snapshot.snapshot_id if latest_snapshot else None,
            snapshot_key=f"{job_id}:completed",
            created_by=existing.user_id,
            user_id=existing.user_id,
        )

    return updated


def mark_generation_job_failed(job_id: str, error: dict, metadata: dict | None = None, *, workspace_id: str | None = None, user_id: str | None = None) -> GenerationJobResponse | None:
    if _use_postgres_backend():
        return _mark_generation_job_failed_db(job_id, error, metadata=metadata, workspace_id=workspace_id, user_id=user_id)
    existing = get_generation_job(job_id, workspace_id=workspace_id, user_id=user_id) if workspace_id or user_id else get_generation_job_internal(job_id)
    if not existing:
        return None
    merged_metadata = _without_pending_interrupt({**existing.metadata, **(metadata or {})})
    progress = existing.progress.model_copy(update={"current_stage": "failed"})
    updated = update_generation_job(
        job_id,
        status="failed",
        progress=progress,
        error=ErrorResponse(
            error_code=str(error.get("error_code") or "generation_job_execution_failed"),
            error_type=error.get("error_type"),
            message=str(error.get("message") or "Generation job execution failed."),
            detail=error.get("detail"),
        ),
        metadata=merged_metadata,
    )
    if updated and existing.thread_id:
        transitioned = chat_thread_service.clear_thread_active_job(existing.thread_id, status="failed", expected_public_job_id=job_id)
        if not transitioned:
            return updated

        # failure event
        chat_thread_service.append_generation_job_chat_event_memory(
            thread_id=existing.thread_id,
            job_id=job_id,
            event_type="generation_failed",
            role="system",
            content=None,
            payload={"job_id": job_id, "error_code": error.get("error_code")},
            user_id=existing.user_id,
        )

        # failed snapshot
        latest_snapshot = state_service.get_latest_thread_state_for_user(
            public_thread_id=existing.thread_id,
            user_id=existing.user_id,
        )
        state_service.save_thread_state_snapshot(
            public_thread_id=existing.thread_id,
            workspace_id=_memory_job_workspace_id(existing) or "mem_workspace",
            snapshot_kind="job_failed",
            state_payload=latest_snapshot.state_payload if latest_snapshot else {},
            changed_fields=[],
            generation_job_id=job_id,
            source_message_id=None,
            parent_snapshot_id=latest_snapshot.snapshot_id if latest_snapshot else None,
            snapshot_key=f"{job_id}:failed",
            metadata={
                "status": "failed",
                "error_code": str(error.get("error_code") or "generation_job_execution_failed"),
                "error_type": str(error.get("error_type") or ""),
            },
            created_by=existing.user_id,
            user_id=existing.user_id,
        )

    return updated


def _parse_iso_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def maybe_mark_stale_generation_job_failed(
    job: GenerationJobResponse,
    *,
    workspace_id: str | None = None,
    user_id: str | None = None,
    now: datetime | None = None,
    stale_after_seconds: int = DEFAULT_STALE_RUNNING_AFTER_SECONDS,
) -> GenerationJobResponse:
    if job.status != "running":
        return job
    if job.progress.current_stage not in STALE_RUNNING_STAGE_NAMES:
        return job
    updated_at = _parse_iso_datetime(job.updated_at)
    if not updated_at:
        return job
    current_time = now or datetime.now(timezone.utc)
    if updated_at.tzinfo is None:
        updated_at = updated_at.replace(tzinfo=timezone.utc)
    if current_time - updated_at < timedelta(seconds=stale_after_seconds):
        return job

    failed = mark_generation_job_failed(
        job.job_id,
        {
            "error_code": "generation_job_stale_running",
            "message": "Generation job stopped while preparing the request.",
            "detail": "The job stayed in running/planning longer than the allowed stale threshold.",
        },
        metadata={
            **(job.metadata or {}),
            "execution_mode": "stale_running_recovered",
            "stale_running_stage": job.progress.current_stage,
        },
        workspace_id=workspace_id,
        user_id=user_id,
    )
    return failed or job


def mark_generation_job_waiting_user_input(
    job_id: str,
    result_state: dict,
    changed_fields: list[str],
    assistant_message: str | None = None,
    *,
    workspace_id: str | None = None,
    user_id: str | None = None,
) -> GenerationJobResponse | None:
    if _use_postgres_backend():
        return _mark_generation_job_waiting_user_input_db(
            job_id,
            result_state,
            changed_fields,
            assistant_message,
            workspace_id=workspace_id,
            user_id=user_id,
        )

    existing = get_generation_job(job_id, workspace_id=workspace_id, user_id=user_id) if workspace_id or user_id else get_generation_job(job_id)
    if not existing:
        return None

    progress = existing.progress.model_copy(update={"current_stage": "waiting_user_input", "progress_percent": 50})
    pending_interrupt = _pending_interrupt_from_state(result_state)
    metadata = {
        **(existing.metadata or {}),
        "pending_interrupt": pending_interrupt,
        "assistant_message": assistant_message,
        "context": sanitize_chat_payload(result_state.get("context") or {}),
        "missing_fields": sanitize_chat_payload(result_state.get("missing_fields") or []),
    }
    updated = update_generation_job(
        job_id,
        workspace_id=workspace_id,
        user_id=user_id,
        status="waiting_user_input",
        progress=progress,
        metadata=metadata,
    )
    if not updated or not existing.thread_id:
        return updated

    # Assistant message (if any)
    source_message_id = None
    if assistant_message:
        msg = chat_thread_service.append_generation_job_chat_event_memory(
            thread_id=existing.thread_id,
            job_id=job_id,
            event_type="waiting_user_input",
            role="assistant",
            content=assistant_message,
            payload={
                "source": "graph_interrupt",
                "status": "waiting_user_input",
            },
            user_id=existing.user_id,
        )
    else:
        msg = chat_thread_service.append_generation_job_chat_event_memory(
            thread_id=existing.thread_id,
            job_id=job_id,
            event_type="waiting_user_input",
            role="system",
            content=None,
            payload={
                "job_id": job_id,
                "status": "waiting_user_input",
            },
            user_id=existing.user_id,
        )

    if msg:
        source_message_id = msg.message_id

    # Snapshot
    latest_snapshot = state_service.get_latest_thread_state_for_user(
        public_thread_id=existing.thread_id,
        user_id=existing.user_id,
    )
    state_service.save_thread_state_snapshot(
        public_thread_id=existing.thread_id,
        workspace_id=_memory_job_workspace_id(existing) or "mem_workspace",
        snapshot_kind="waiting_user_input",
        state_payload=result_state,
        changed_fields=changed_fields,
        generation_job_id=job_id,
        source_message_id=source_message_id,
        parent_snapshot_id=latest_snapshot.snapshot_id if latest_snapshot else None,
        snapshot_key=f"{job_id}:waiting",
        created_by=existing.user_id,
        user_id=existing.user_id,
    )

    # Release thread active job so next turn can start
    chat_thread_service.clear_thread_active_job(
        existing.thread_id,
        status="draft",
        expected_public_job_id=job_id,
    )

    return updated


def reset_generation_job_store_for_tests() -> None:
    with _GENERATION_JOB_LOCK:
        _GENERATION_JOBS.clear()
        _GENERATION_JOB_WORKSPACES.clear()
    # Memory generation jobs create chat threads; clear them too so the
    # per-workspace thread limit does not leak across tests.
    chat_thread_service.reset_chat_thread_store_for_tests()


def _pending_interrupt_from_state(result_state: dict) -> dict | None:
    interrupts = result_state.get("__interrupt__") or []
    if not isinstance(interrupts, (list, tuple)):
        return None
    if not interrupts:
        return None
    raw_value = getattr(interrupts[0], "value", None)
    if not isinstance(raw_value, dict):
        return None
    return sanitize_chat_payload(raw_value)


def _without_pending_interrupt(metadata: dict | None) -> dict:
    cleaned = dict(metadata or {})
    cleaned.pop("pending_interrupt", None)
    cleaned.pop("assistant_message", None)
    return cleaned


def sanitize_generation_job_metadata_for_api(metadata: dict | None) -> dict:
    def sanitize_public(value):
        if isinstance(value, dict):
            output = {}
            for key, item in value.items():
                normalized = str(key).lower()
                if normalized in PUBLIC_METADATA_BLOCKED_KEYS or normalized in _BLOCKED_METADATA_KEYS:
                    continue
                output[key] = sanitize_public(item)
            return output
        if isinstance(value, list):
            return [sanitize_public(item) for item in value[:50]]
        if isinstance(value, str):
            return value[:500] + "..." if len(value) > 500 else value
        return value

    sanitized = sanitize_public(metadata or {})
    return {
        key: value
        for key, value in sanitized.items()
        if str(key).lower() not in PUBLIC_METADATA_BLOCKED_KEYS
    }


def should_route_generation_job_to_modal(request: GenerationJobCreateRequest) -> bool:
    return (
        modal_settings.get_t2i_execution_backend() == "modal"
        and is_modal_eligible_run_mode(request.run_mode)
    )


def maybe_submit_generation_job_to_modal(
    job: GenerationJobResponse,
    request: GenerationJobCreateRequest,
) -> GenerationJobResponse:
    if not should_route_generation_job_to_modal(request):
        return job
    if not _use_postgres_backend():
        return mark_generation_job_failed(
            job.job_id,
            {
                "error_code": "modal_execution_requires_postgres",
                "message": "Modal execution requires postgres GenerationJob persistence.",
            },
            metadata={"execution_backend": "modal"},
        ) or job
    if not modal_settings.is_modal_execution_enabled():
        return mark_generation_job_failed(
            job.job_id,
            {
                "error_code": "modal_execution_not_enabled",
                "message": "Modal execution is disabled.",
            },
            metadata={"execution_backend": "modal"},
        ) or job

    job_row = generation_job_repo.get_generation_job_row(job.job_id)
    if not job_row:
        return job
    modal_request = build_modal_t2i_request_from_job(job_row=job_row, generation_request=request)
    try:
        submit_generation_job_to_modal(job_row=job_row, modal_request=modal_request)
    except ModalExecutionError as exc:
        return mark_generation_job_failed(
            job.job_id,
            {
                "error_code": "modal_submit_failed",
                "message": "Modal job submit failed.",
                "detail": str(exc),
            },
            metadata={"execution_backend": "modal", "modal_submit_failed": True},
        ) or job
    return get_generation_job(job.job_id) or job


def maybe_poll_generation_job_from_modal(
    job: GenerationJobResponse,
    *,
    workspace_id: str | None = None,
    user_id: str | None = None,
) -> GenerationJobResponse:
    graph_modal_pending = bool((job.metadata or {}).get("graph_modal_pending"))
    if graph_modal_pending:
        if job.status not in {"queued", "running"}:
            return job
        try:
            from orchestrator.app.generation_jobs.execution import poll_and_process_graph_modal_generation_job

            polled = poll_and_process_graph_modal_generation_job(job.job_id, workspace_id=workspace_id, user_id=user_id)
        except ModalJobPollError as exc:
            if _use_postgres_backend():
                job_row = (
                    generation_job_repo.get_generation_job_scoped_by_public_id(job.job_id, workspace_id=_require_workspace_uuid(workspace_id))
                    if workspace_id
                    else generation_job_repo.get_generation_job_row(job.job_id)
                )
                if job_row:
                    _record_generation_job_event_db(
                        job_row,
                        "graph_modal_poll_unavailable",
                        payload={
                            "error_code": "modal_poll_adapter_unavailable",
                            "message": str(exc),
                        },
                    )
            return job
        except ModalExecutionError as exc:
            return mark_generation_job_failed(
                job.job_id,
                {
                    "error_code": "graph_modal_poll_failed",
                    "message": "Graph Modal job poll failed.",
                    "detail": str(exc),
                },
                metadata={"execution_backend": "modal", "execution_mode": "graph_modal_poll_failed"},
                workspace_id=workspace_id,
                user_id=user_id,
            ) or job
        return polled or job

    if not _use_postgres_backend():
        return job
    if not modal_settings.is_modal_poll_on_get_enabled():
        return job
    if job.status not in {"queued", "running"}:
        return job
    job_row = (
        generation_job_repo.get_generation_job_scoped_by_public_id(job.job_id, workspace_id=_require_workspace_uuid(workspace_id))
        if workspace_id
        else generation_job_repo.get_generation_job_row(job.job_id)
    )
    if not job_row or not job_row.get("modal_call_id"):
        return job
    try:
        polled = poll_and_process_modal_generation_job(job_id=job.job_id)
    except ModalJobPollError as exc:
        job_row = (
            generation_job_repo.get_generation_job_scoped_by_public_id(job.job_id, workspace_id=_require_workspace_uuid(workspace_id))
            if workspace_id
            else generation_job_repo.get_generation_job_row(job.job_id)
        )
        if job_row:
            _record_generation_job_event_db(
                job_row,
                "modal_poll_unavailable",
                payload={
                    "error_code": "modal_poll_adapter_unavailable",
                    "message": str(exc),
                },
            )
        return job
    except ModalExecutionError as exc:
        return mark_generation_job_failed(
            job.job_id,
            {
                "error_code": "modal_poll_failed",
                "message": "Modal job poll failed.",
                "detail": str(exc),
            },
            metadata={"execution_backend": "modal", "modal_poll_failed": True},
            workspace_id=workspace_id,
            user_id=user_id,
        ) or job
    return polled or job


def _normalize_engine_preference(value: object) -> str | None:
    if value is None:
        return None
    normalized = str(value).strip().lower().replace("-", "_")
    aliases = {
        "gpt_image_1": "gpt_image_1",
        "gpt_image1": "gpt_image_1",
        "gptimage1": "gpt_image_1",
        "gpt_image_2": "gpt_image_2",
        "gpt_image2": "gpt_image_2",
        "gptimage2": "gpt_image_2",
        "flux": "flux2_klein_4b",
        "flux_schnell": "flux2_klein_4b",
        "flux_1_schnell": "flux2_klein_4b",
        "flux2_klein": "flux2_klein_4b",
        "flux2_klein_4b": "flux2_klein_4b",
        "flux_2_klein_4b": "flux2_klein_4b",
        "sd35": "sd35_large",
        "sd35_large": "sd35_large",
        "sd3_5_large": "sd35_large",
    }
    return aliases.get(normalized)


def _engine_preference(run_mode: str) -> str | None:
    if run_mode in {"gpt_image_1_actual", "gpt_image_1_smoke"}:
        return "gpt_image_1"
    if run_mode in {"gpt_image_2_actual", "gpt_image_2_smoke"}:
        return "gpt_image_2"
    if run_mode in {"sd35_local", "sd35_local_smoke", "sd35_large_real"}:
        return "sd35_large"
    if run_mode in {"flux_local", "flux_local_smoke", "flux_schnell_real", "flux", "flux_smoke", "flux2_klein_4b"}:
        return "flux2_klein_4b"
    return None


def _engine_preference_for_request(request: GenerationJobCreateRequest) -> str | None:
    metadata = request.metadata or {}
    for key in ("requested_engine", "t2i_engine", "selected_engine", "engine"):
        engine = _normalize_engine_preference(metadata.get(key))
        if engine:
            return engine
    return _engine_preference(request.run_mode)


def _apply_generation_engine_to_state(restored_payload: dict, request: GenerationJobCreateRequest) -> None:
    engine = _engine_preference_for_request(request)
    if not engine:
        return
    restored_payload["engine"] = engine
    current_brief = restored_payload.setdefault("current_brief", {})
    if isinstance(current_brief, dict):
        current_brief["requested_engine"] = engine
        current_brief["engine"] = engine


def _model_provider_for_run_mode(run_mode: str) -> str | None:
    if run_mode in {"mock_immediate"}:
        return "mock"
    if run_mode in {"gpt_image_1_actual", "gpt_image_1_smoke", "gpt_image_2_actual", "gpt_image_2_smoke"}:
        return "openai"
    if run_mode in {
        "sd35_local",
        "sd35_local_smoke",
        "sd35_large_real",
        "flux_local",
        "flux_local_smoke",
        "flux_schnell_real",
        "flux",
        "flux_smoke",
        "flux2_klein_4b",
    }:
        return "local"
    return None


def _model_provider_for_request(request: GenerationJobCreateRequest) -> str | None:
    if modal_settings.get_t2i_execution_backend() == "modal" and is_modal_eligible_run_mode(request.run_mode):
        return "modal"
    return _model_provider_for_run_mode(request.run_mode)


def _model_name_for_run_mode(run_mode: str) -> str | None:
    return _engine_preference(run_mode)


def _db_uuid_or_none(value: str | None) -> str | None:
    if not value:
        return None
    try:
        return str(UUID(str(value)))
    except (TypeError, ValueError):
        return None


def _require_workspace_uuid(value: str | None) -> str:
    if not value:
        raise GenerationJobWorkspaceRequired("workspaceId is required.")
    try:
        return str(UUID(str(value)))
    except (TypeError, ValueError) as exc:
        raise GenerationJobInvalidWorkspaceId("workspaceId must be a UUID.") from exc


def _use_postgres_backend() -> bool:
    return db_settings.get_db_backend() == "postgres"


def resolve_scoped_workspace_id(workspace_id: str | None, user_id: str | None, account_type: str | None = None) -> str:
    """Resolve a concrete workspace id for scoped (public) job access.

    HITL polling/answer only carry the authenticated user (no explicit
    workspace id). Mirror the create-path resolution so those requests do not
    fail with "workspaceId is required.".
    """
    requested = (workspace_id or "").strip()
    resolved_user_id = (user_id or "").strip() or None
    # Explicit workspace always wins (ownership is validated downstream).
    if requested:
        return _require_workspace_uuid(requested) if _use_postgres_backend() else requested
    # No explicit workspace: resolve from the authenticated user. Reject only
    # when there is no identity at all (preserves missing-scope rejection).
    if not resolved_user_id and not db_settings.allow_demo_workspace_fallback():
        raise GenerationJobWorkspaceRequired("workspaceId is required.")
    if not _use_postgres_backend():
        return "mem_workspace"
    if resolved_user_id:
        with db_transaction() as conn:
            workspace = workspace_repo.ensure_user_workspace(
                user_id=resolved_user_id,
                account_type=account_type,
                connection=conn,
            )
        return str(workspace["id"])
    with db_transaction() as conn:
        workspace = workspace_repo.ensure_demo_workspace(user_id=db_settings.get_demo_user_id(), connection=conn)
    return str(workspace["id"])


def _memory_job_workspace_id(job: GenerationJobResponse) -> str | None:
    return _GENERATION_JOB_WORKSPACES.get(job.job_id) or "mem_workspace"


def _resolve_db_workspace_for_generation_request(request: GenerationJobCreateRequest, *, connection: object) -> dict:
    requested_workspace_id = (request.workspace_id or "").strip()
    user_id = (request.user_id or "").strip() or None
    if requested_workspace_id:
        workspace_id = _require_workspace_uuid(requested_workspace_id)
        if not user_id and not db_settings.allow_demo_workspace_fallback():
            raise GenerationJobAuthenticationRequired("Authenticated user is required.")
        if user_id:
            workspace = workspace_repo.get_workspace_for_user(workspace_id=workspace_id, user_id=user_id, connection=connection)
        else:
            workspace = workspace_repo.get_workspace(workspace_id, connection=connection)
        if not workspace:
            raise GenerationJobWorkspaceNotFound("Workspace was not found.")
        return workspace
    if user_id:
        return workspace_repo.ensure_user_workspace(
            user_id=user_id,
            account_type=request.account_type or "user",
            connection=connection,
        )
    if db_settings.allow_demo_workspace_fallback():
        user_id = user_id or db_settings.get_demo_user_id()
        return workspace_repo.ensure_demo_workspace(user_id=user_id, connection=connection)
    raise GenerationJobWorkspaceRequired("workspaceId is required.")


def _resolve_db_workspace_for_public_access(
    *,
    requested_workspace_id: str | None,
    user_id: str | None,
    connection: object | None = None,
) -> str:
    workspace_id = (requested_workspace_id or "").strip()
    resolved_user_id = (user_id or "").strip() or None
    if not workspace_id:
        if resolved_user_id:
            workspace = workspace_repo.ensure_user_workspace(user_id=resolved_user_id, connection=connection)
            return str(workspace["id"])
        if db_settings.allow_demo_workspace_fallback():
            resolved_user_id = resolved_user_id or db_settings.get_demo_user_id()
            workspace = workspace_repo.ensure_demo_workspace(user_id=resolved_user_id, connection=connection)
            return str(workspace["id"])
        raise GenerationJobWorkspaceRequired("workspaceId is required.")
    workspace_uuid = _require_workspace_uuid(workspace_id)
    if not resolved_user_id and not db_settings.allow_demo_workspace_fallback():
        raise GenerationJobAuthenticationRequired("Authenticated user is required.")
    if resolved_user_id:
        workspace = workspace_repo.get_workspace_for_user(workspace_id=workspace_uuid, user_id=resolved_user_id, connection=connection)
    else:
        workspace = workspace_repo.get_workspace(workspace_uuid, connection=connection)
    if not workspace:
        raise GenerationJobWorkspaceNotFound("Workspace was not found.")
    return str(workspace["id"])


def _resolve_generation_input_asset(
    *,
    public_asset_id: str,
    workspace_id: str,
    expected_kind: str,
    connection: object,
) -> dict:
    from orchestrator.app.generation_jobs.errors import (
        GenerationJobAssetKindInvalid,
        GenerationJobAssetNotFound,
        GenerationJobAssetNotReady,
    )
    from orchestrator.app.db.repositories import assets as asset_repo

    row = asset_repo.get_asset_by_public_id(
        public_asset_id,
        workspace_id=workspace_id,
        connection=connection,
    )
    if not row:
        raise GenerationJobAssetNotFound(
            f"{expected_kind} asset was not found."
        )

    if row.get("kind") != expected_kind:
        raise GenerationJobAssetKindInvalid(
            f"Expected asset kind={expected_kind}."
        )

    upload_status = (
        (row.get("metadata") or {})
        .get("upload", {})
        .get("status")
    )
    if upload_status != "ready":
        raise GenerationJobAssetNotReady(
            f"{expected_kind} asset is not ready."
        )

    return row


def _create_generation_job_db(request: GenerationJobCreateRequest) -> GenerationJobResponse:
    now = _now_iso()
    effective_run_mode, execution_mode = _initial_run_mode_metadata(request.run_mode)
    user_id = request.user_id or db_settings.get_demo_user_id()
    public_job_id = f"job_{uuid4().hex}"
    prompt_preview = _preview_user_input(request.user_input)
    request_payload = _request_payload_summary(request)
    engine_preference = _engine_preference_for_request(request)
    r2_usage_payload: dict | None = None
    with db_transaction() as conn:
        workspace = _resolve_db_workspace_for_generation_request(request, connection=conn)
        workspace_id = str(workspace["id"])

        # thread reuse or create
        if request.thread_id:
            thread_row = chat_thread_repo.get_chat_thread_by_public_id(
                request.thread_id,
                workspace_id=workspace_id,
                connection=conn,
                for_update=True,
            )
            if not thread_row:
                raise ChatThreadNotFoundError()
            if thread_row.get("archived_at"):
                raise ChatThreadArchivedError()
            if thread_row.get("active_job_id"):
                raise ChatThreadHasActiveJobError()
            thread = thread_row
        else:
            thread = chat_thread_repo.create_chat_thread(
                workspace_id=workspace_id,
                created_by=user_id,
                title=_preview_user_input(request.user_input, max_length=80),
                brand_kit_id=_db_uuid_or_none(request.brand_kit_id),
                connection=conn,
            )

        # Resolve assets
        input_asset_uuid: str | None = None
        reference_asset_uuid: str | None = None
        
        if request.source_asset_id:
            asset_row = _resolve_generation_input_asset(
                public_asset_id=request.source_asset_id,
                workspace_id=workspace_id,
                expected_kind="source",
                connection=conn,
            )
            input_asset_uuid = str(asset_row["id"])
            
        if request.reference_asset_id:
            asset_row = _resolve_generation_input_asset(
                public_asset_id=request.reference_asset_id,
                workspace_id=workspace_id,
                expected_kind="reference",
                connection=conn,
            )
            reference_asset_uuid = str(asset_row["id"])

        metadata = {
            "requested_run_mode": request.run_mode,
            "effective_run_mode": effective_run_mode,
            "execution_mode": execution_mode,
            "account_type": request.account_type or ("guest" if str(request.user_id or "").startswith("guest_") else "user"),
            "user_input_preview": prompt_preview,
            "brand_kit_id": request.brand_kit_id,
            "user_id": request.user_id,
            "entry_mode": request.entry_mode,
            "copy_generation_mode": request.copy_generation_mode,
            "user_plan": request.user_plan,
            "selected_reference_template_id": request.selected_reference_template_id,
            "source_asset_id": request.source_asset_id,
            "reference_asset_id": request.reference_asset_id,
            "ad_format": request.ad_format,
            "public_thread_id": thread.get("public_thread_id"),
            "engine_preference": engine_preference,
            "t2i_engine": engine_preference,
            **_safe_request_metadata(request.metadata),
        }
        row = generation_job_repo.create_generation_job_row(
            public_job_id=public_job_id,
            workspace_id=workspace_id,
            thread_id=str(thread["id"]) if thread.get("id") else None,
            requested_by=user_id,
            status="queued",
            current_stage="queued",
            progress_percent=0,
            selected_reference_template_id=request.selected_reference_template_id,
            input_asset_id=input_asset_uuid,
            reference_asset_id=reference_asset_uuid,
            output_path=None,
            result_payload=None,
            error=None,
            metadata=metadata,
            run_mode=request.run_mode,
            engine=engine_preference,
            model_provider=_model_provider_for_request(request),
            model_name=engine_preference,
            prompt_hash=hashlib.sha256(request.user_input.encode("utf-8")).hexdigest(),
            prompt_preview=prompt_preview,
            request_payload=request_payload,
            connection=conn,
        )

        # 1. User message save
        msg_row = chat_message_repo.append_chat_message(
            public_thread_id=thread.get("public_thread_id"),
            workspace_id=workspace_id,
            role="user",
            content=request.user_input,
            payload={"source": "generation_job_input"},
            created_by=user_id,
            generation_job_id=str(row["id"]),
            event_type="user_input",
            connection=conn,
        )

        # 2. State snapshot merge and save
        latest_snapshot = state_service.get_latest_thread_state_snapshot(
            public_thread_id=thread.get("public_thread_id"),
            workspace_id=workspace_id,
            connection=conn,
        )

        explicit_fields = {}
        for k in request.model_fields_set:
            if k in [
                "ad_format",
                "copy_generation_mode",
                "selected_reference_template_id",
                "source_image_path",
                "reference_image_path",
                "source_asset_id",
                "reference_asset_id",
                "selected_copy_id",
                "selected_channel_id",
                "selected_tone",
                "custom_direction",
                "user_custom_headline",
                "user_custom_subcopy",
                "brand_kit_id",
                "user_plan",
            ]:
                explicit_fields[k] = getattr(request, k)

        restored_payload = state_service.restore_thread_state(
            latest_snapshot,
            current_request_fields=explicit_fields,
            user_input=request.user_input,
        )
        _apply_generation_engine_to_state(restored_payload, request)
        changed_fields = calculate_changed_fields(
            latest_snapshot.state_payload if latest_snapshot else None,
            restored_payload
        )

        from orchestrator.app.reference_catalog.service import get_reference_template
        from orchestrator.app.brand_kits.service import get_brand_kit

        def _build_ref_snapshot_db(tid: str | None):
            if not tid: return {}
            t = get_reference_template(tid)
            if not t: return {}
            d = t.model_dump(mode="json")
            return {
                "template_id": d.get("template_id"),
                "category": d.get("category"),
                "business_type": d.get("business_types", d.get("business_type")),
                "style_keywords": d.get("style_keywords"),
                "color_palette": d.get("color_palette"),
                "composition": d.get("composition"),
                "reserved_text_areas": d.get("reserved_text_areas"),
                "aspect_ratio": d.get("aspect_ratio"),
            }

        def _build_brand_snapshot_db(bid: str | None):
            if not bid: return {}
            b = get_brand_kit(bid)
            if not b: return {}
            d = b.model_dump(mode="json")
            return {
                "brand_kit_id": d.get("brand_kit_id"),
                "brand_name": d.get("brand_name"),
                "primary_color": d.get("primary_color"),
                "secondary_color": d.get("secondary_color"),
                "fonts": d.get("fonts"),
            }

        # Use restored effective IDs if request didn't explicitly override
        effective_reference_id = restored_payload.get("selected_reference_template_id")
        effective_brand_kit_id = restored_payload.get("brand_kit_id")

        snapshot_kind = "restored_input" if latest_snapshot else "input"
        state_service.save_thread_state_snapshot(
            public_thread_id=thread.get("public_thread_id"),
            workspace_id=workspace_id,
            snapshot_kind=snapshot_kind,
            state_payload=restored_payload,
            changed_fields=changed_fields,
            generation_job_id=str(row["id"]),
            source_message_id=str(msg_row["id"]) if msg_row else None,
            parent_snapshot_id=latest_snapshot.snapshot_id if latest_snapshot else None,
            selected_reference_template_id=effective_reference_id,
            reference_template_snapshot=_build_ref_snapshot_db(effective_reference_id),
            brand_kit_snapshot=_build_brand_snapshot_db(effective_brand_kit_id),
            snapshot_key=f"{public_job_id}:input",
            created_by=user_id,
            connection=conn,
        )

        claimed = chat_thread_repo.set_chat_thread_active_job(
            thread.get("public_thread_id") or str(thread["id"]),
            active_job_id=str(row["id"]) if row.get("id") else None,
            status="generating",
            workspace_id=workspace_id,
            connection=conn,
        )
        if not claimed:
            raise ChatThreadHasActiveJobError()

        # Queued event
        chat_message_repo.append_generation_job_chat_event(
            public_thread_id=thread.get("public_thread_id"),
            workspace_id=workspace_id,
            generation_job_id=str(row["id"]),
            event_type="generation_queued",
            role="system",
            content=None,
            payload={"job_id": public_job_id, "status": "queued"},
            created_by=user_id,
            connection=conn,
        )
        _record_generation_job_event_db(row, "queued", payload={"run_mode": request.run_mode}, connection=conn)
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


def _get_generation_job_db(job_id: str, *, workspace_id: str | None = None, user_id: str | None = None) -> GenerationJobResponse | None:
    if workspace_id is None or user_id is None:
        raise GenerationJobWorkspaceRequired("Authenticated workspace scope is required.")
    resolved_workspace_id = _resolve_db_workspace_for_public_access(requested_workspace_id=workspace_id, user_id=user_id)
    row = generation_job_repo.get_generation_job_scoped_by_public_id(job_id, workspace_id=resolved_workspace_id)
    return _job_response_from_db_row(row)


def _append_generation_job_user_answer_message_db(job_id: str, answer: GenerationJobAnswerRequest, content: str, *, workspace_id: str | None = None, user_id: str | None = None) -> None:
    with db_transaction() as conn:
        if workspace_id:
            resolved_workspace_id = _resolve_db_workspace_for_public_access(requested_workspace_id=workspace_id, user_id=user_id, connection=conn)
            row = generation_job_repo.get_generation_job_scoped_by_public_id(job_id, workspace_id=resolved_workspace_id, connection=conn)
        else:
            row = generation_job_repo.get_generation_job_internal_by_public_id(job_id, connection=conn)
        if not row or not row.get("thread_id"):
            return
        chat_message_repo.append_chat_message(
            public_thread_id=_thread_public_or_internal(row),
            workspace_id=str(row["workspace_id"]),
            role="user",
            content=content,
            payload={
                **_answer_message_payload(answer),
                "job_id": job_id,
            },
            created_by=row.get("requested_by"),
            generation_job_id=str(row["id"]),
            event_type="user_answer",
            connection=conn,
        )


def _update_generation_job_db(job_id: str, *, workspace_id: str | None = None, user_id: str | None = None, **fields) -> GenerationJobResponse | None:
    existing = get_generation_job(job_id, workspace_id=workspace_id, user_id=user_id)
    if not existing:
        return None
    row_fields = _db_update_fields(existing, fields)
    resolved_workspace_id = None
    if workspace_id is not None or user_id is not None:
        resolved_workspace_id = _resolve_db_workspace_for_public_access(requested_workspace_id=workspace_id, user_id=user_id)
    row = generation_job_repo.update_generation_job_row(job_id, workspace_id=resolved_workspace_id, **row_fields)
    return _job_response_from_db_row(row)


def _mark_generation_job_running_db(job_id: str, stage: str, *, workspace_id: str | None = None, user_id: str | None = None) -> GenerationJobResponse | None:
    with db_transaction() as conn:
        resolved_workspace_id = None
        if workspace_id is not None or user_id is not None:
            resolved_workspace_id = _resolve_db_workspace_for_public_access(requested_workspace_id=workspace_id, user_id=user_id, connection=conn)
        running_kwargs = {}
        if resolved_workspace_id:
            running_kwargs["workspace_id"] = resolved_workspace_id
        row = generation_job_repo.mark_generation_job_running_row(job_id, current_stage=stage, connection=conn, **running_kwargs)
        if not row:
            return None
        cleaned_metadata = _without_pending_interrupt(row.get("metadata") or {})
        if cleaned_metadata != (row.get("metadata") or {}):
            row = generation_job_repo.update_generation_job_row(job_id, metadata=cleaned_metadata, connection=conn) or row
        _record_generation_job_event_db(row, "running", message=stage, payload={"current_stage": stage}, connection=conn)
        if row.get("thread_id"):
            chat_thread_repo.update_chat_thread_status(
                _thread_public_or_internal(row),
                status="generating",
                active_job_id=str(row["id"]) if row.get("id") else None,
                connection=conn,
            )
    return _job_response_from_db_row(row)


def _mark_generation_job_done_db(
    job_id: str,
    result_payload: dict,
    output_path: str | None = None,
    metadata: dict | None = None,
    *,
    workspace_id: str | None = None,
    user_id: str | None = None,
) -> GenerationJobResponse | None:
    with db_transaction() as conn:
        if workspace_id is not None or user_id is not None:
            resolved_workspace_id = _resolve_db_workspace_for_public_access(requested_workspace_id=workspace_id, user_id=user_id, connection=conn)
            existing = generation_job_repo.get_generation_job_scoped_by_public_id(job_id, workspace_id=resolved_workspace_id, connection=conn, for_update=True)
        else:
            resolved_workspace_id = None
            existing = generation_job_repo.get_generation_job_row(job_id, connection=conn)
        if not existing:
            return None

        thread_row = chat_thread_repo.get_chat_thread_by_public_id(
            _thread_public_or_internal(existing),
            workspace_id=str(existing["workspace_id"]),
            connection=conn,
            for_update=True,
        )
        if thread_row and str(thread_row.get("active_job_id")) != str(existing.get("id")):
            _record_generation_job_event_db(existing, "stale_completion_ignored", message="Stale job ignored.", connection=conn)
            return _job_response_from_db_row(existing)

        merged_metadata = _without_pending_interrupt({**(existing.get("metadata") or {}), **(metadata or {})})
        final_path = _resolve_final_artifact_path(result_payload, output_path)
        if storage_settings.is_r2_upload_required() and not final_path and not _has_browser_result_url(result_payload):
            return _mark_generation_job_failed_from_row_db(
                existing,
                {
                    "error_code": "result_artifact_url_missing",
                    "message": "Generated image artifact is missing a browser-usable URL.",
                    "detail": "R2 upload is required, but the generation result did not include a final artifact path or URL.",
                },
                metadata={**merged_metadata, "storage_warning": "result_artifact_url_missing_required"},
                connection=conn,
            )
        done_kwargs = {}
        if resolved_workspace_id:
            done_kwargs["workspace_id"] = resolved_workspace_id
        row = generation_job_repo.mark_generation_job_done_row(
            job_id,
            result_payload=result_payload,
            output_path=final_path,
            metadata=merged_metadata,
            connection=conn,
            **done_kwargs,
        )
        if not row:
            return None

        try:
            output, row, r2_usage_payload = _create_output_records_for_done_job_db(
                row,
                result_payload,
                final_path,
                connection=conn,
                include_usage_payload=True,
            )
        except AssetStorageError as exc:
            return _mark_generation_job_failed_from_row_db(
                row,
                {
                    "error_code": "r2_upload_failed",
                    "message": "R2 upload failed.",
                    "detail": str(exc),
                },
                metadata={**merged_metadata, "storage_warning": "r2_upload_failed_required"},
                connection=conn,
            )

        _record_generation_job_event_db(
            row,
            "done",
            payload={
                "output_path": final_path,
                "storage_provider": (row.get("result_payload") or {}).get("storage_provider"),
                "final_image_url_present": bool((row.get("result_payload") or {}).get("final_image_url")),
                "download_url_present": bool((row.get("result_payload") or {}).get("download_url")),
            },
            connection=conn,
        )
        final_brief = (row.get("result_payload") or {}).get("final_brief") or merged_metadata.get("final_brief")
        completed_thread = chat_thread_repo.complete_chat_thread_generation(
            public_thread_id=_thread_public_or_internal(row),
            workspace_id=str(row["workspace_id"]),
            expected_active_job_id=str(row["id"]) if row.get("id") else None,
            final_output_id=str(output["id"]) if output and output.get("id") else None,
            final_brief=sanitize_chat_payload(final_brief) if final_brief is not None else None,
            connection=conn,
        )

        if not completed_thread:
            _record_generation_job_event_db(row, "stale_completion_ignored", message="Stale job ignored.", connection=conn)
            return _job_response_from_db_row(row)

        # 1. system event for completion
        chat_message_repo.append_generation_job_chat_event(
            public_thread_id=_thread_public_or_internal(row),
            workspace_id=str(row["workspace_id"]),
            generation_job_id=str(row["id"]),
            event_type="generation_completed",
            role="system",
            content="Generation completed.",
            payload={"job_id": job_id, "has_output": True},
            created_by=row.get("requested_by"),
            connection=conn,
        )

        # 2. completed snapshot
        latest_snapshot = state_service.get_latest_thread_state_snapshot(
            public_thread_id=_thread_public_or_internal(row),
            workspace_id=str(row["workspace_id"]),
            connection=conn,
        )
        final_payload = latest_snapshot.state_payload if latest_snapshot else {}
        # If result_payload has new data, merge it safely. In execution phase graph_completed handles full state.

        state_service.save_thread_state_snapshot(
            public_thread_id=_thread_public_or_internal(row),
            workspace_id=str(row["workspace_id"]),
            snapshot_kind="job_completed",
            state_payload=final_payload,
            changed_fields=[],
            generation_job_id=str(row["id"]),
            source_message_id=None,
            parent_snapshot_id=latest_snapshot.snapshot_id if latest_snapshot else None,
            snapshot_key=f"{job_id}:completed",
            created_by=row.get("requested_by"),
            connection=conn,
        )

        if output:
            _record_generation_job_event_db(
                row,
                "output_created",
                payload={
                    "output_id": _string_or_none(output.get("id")),
                    "asset_id": _string_or_none(output.get("asset_id")),
                },
                connection=conn,
            )
    if r2_usage_payload:
        _safe_record_r2_usage(r2_usage_payload)
    return _job_response_from_db_row(row)


def _mark_generation_job_failed_db(job_id: str, error: dict, metadata: dict | None = None, *, workspace_id: str | None = None, user_id: str | None = None) -> GenerationJobResponse | None:
    error_payload = {
        "error_code": str(error.get("error_code") or "generation_job_execution_failed"),
        "error_type": error.get("error_type"),
        "message": str(error.get("message") or "Generation job execution failed."),
        "detail": error.get("detail"),
    }
    with db_transaction() as conn:
        if workspace_id is not None or user_id is not None:
            resolved_workspace_id = _resolve_db_workspace_for_public_access(requested_workspace_id=workspace_id, user_id=user_id, connection=conn)
            existing = generation_job_repo.get_generation_job_scoped_by_public_id(job_id, workspace_id=resolved_workspace_id, connection=conn, for_update=True)
        else:
            resolved_workspace_id = None
            existing = generation_job_repo.get_generation_job_row(job_id, connection=conn)
        if not existing:
            return None

        thread_row = chat_thread_repo.get_chat_thread_by_public_id(
            _thread_public_or_internal(existing),
            workspace_id=str(existing["workspace_id"]),
            connection=conn,
            for_update=True,
        )
        if thread_row and str(thread_row.get("active_job_id")) != str(existing.get("id")):
            _record_generation_job_event_db(existing, "stale_failure_ignored", message="Stale failure ignored.", connection=conn)
            return _job_response_from_db_row(existing)

        merged_metadata = _without_pending_interrupt({**(existing.get("metadata") or {}), **(metadata or {})})
        failed_kwargs = {}
        if resolved_workspace_id:
            failed_kwargs["workspace_id"] = resolved_workspace_id
        row = generation_job_repo.mark_generation_job_failed_row(job_id, error_payload, metadata=merged_metadata, connection=conn, **failed_kwargs)
        if not row:
            return None
        _record_generation_job_event_db(
            row,
            "failed",
            message=error_payload["message"],
            payload={
                "error_code": error_payload["error_code"],
                "error_type": error_payload.get("error_type"),
                "message": error_payload["message"],
            },
            connection=conn,
        )
        failed_thread = chat_thread_repo.fail_chat_thread_generation(
            public_thread_id=_thread_public_or_internal(row),
            workspace_id=str(row["workspace_id"]),
            expected_active_job_id=str(row["id"]) if row.get("id") else None,
            connection=conn,
        )

        if not failed_thread:
            _record_generation_job_event_db(row, "stale_failure_ignored", message="Stale failure ignored.", connection=conn)
            return _job_response_from_db_row(row)

        # 1. system event for failure
        chat_message_repo.append_generation_job_chat_event(
            public_thread_id=_thread_public_or_internal(row),
            workspace_id=str(row["workspace_id"]),
            generation_job_id=str(row["id"]),
            event_type="generation_failed",
            role="system",
            content=None,
            payload={"job_id": job_id, "error_code": error_payload["error_code"]},
            created_by=row.get("requested_by"),
            connection=conn,
        )

        # 2. failed snapshot
        latest_snapshot = state_service.get_latest_thread_state_snapshot(
            public_thread_id=_thread_public_or_internal(row),
            workspace_id=str(row["workspace_id"]),
            connection=conn,
        )
        state_service.save_thread_state_snapshot(
            public_thread_id=_thread_public_or_internal(row),
            workspace_id=str(row["workspace_id"]),
            snapshot_kind="job_failed",
            state_payload=latest_snapshot.state_payload if latest_snapshot else {},
            changed_fields=[],
            generation_job_id=str(row["id"]),
            source_message_id=None,
            parent_snapshot_id=latest_snapshot.snapshot_id if latest_snapshot else None,
            snapshot_key=f"{job_id}:failed",
            metadata={
                "status": "failed",
                "error_code": error_payload["error_code"],
                "error_type": error_payload.get("error_type", ""),
            },
            created_by=row.get("requested_by"),
            connection=conn,
        )
    return _job_response_from_db_row(row)

def _mark_generation_job_waiting_user_input_db(
    job_id: str,
    result_state: dict,
    changed_fields: list[str],
    assistant_message: str | None = None,
    *,
    workspace_id: str | None = None,
    user_id: str | None = None,
) -> GenerationJobResponse | None:
    with db_transaction() as conn:
        if workspace_id is not None or user_id is not None:
            resolved_workspace_id = _resolve_db_workspace_for_public_access(
                requested_workspace_id=workspace_id, user_id=user_id, connection=conn
            )
            existing = generation_job_repo.get_generation_job_scoped_by_public_id(
                job_id, workspace_id=resolved_workspace_id, connection=conn, for_update=True
            )
        else:
            resolved_workspace_id = None
            existing = generation_job_repo.get_generation_job_row(job_id, connection=conn)
        if not existing:
            return None
        pending_interrupt = _pending_interrupt_from_state(result_state)
        metadata = {
            **(existing.get("metadata") or {}),
            "pending_interrupt": pending_interrupt,
            "assistant_message": assistant_message,
            "context": sanitize_chat_payload(result_state.get("context") or {}),
            "missing_fields": sanitize_chat_payload(result_state.get("missing_fields") or []),
        }

        public_thread_id = _thread_public_or_internal(existing)
        workspace_id = str(existing["workspace_id"])
        user_id = existing.get("requested_by")

        # Release thread active job so next turn can start
        paused_thread = chat_thread_repo.pause_chat_thread_generation(
            public_thread_id=public_thread_id,
            workspace_id=workspace_id,
            expected_active_job_id=str(existing["id"]),
            connection=conn,
        )

        if not paused_thread:
            _record_generation_job_event_db(existing, "stale_waiting_ignored", message="Stale waiting ignored.", connection=conn)
            return _job_response_from_db_row(existing)

        update_kwargs = {}
        if resolved_workspace_id:
            update_kwargs["workspace_id"] = resolved_workspace_id
        row = generation_job_repo.update_generation_job_row(
            job_id,
            status="waiting_user_input",
            current_stage="waiting_user_input",
            progress_percent=50,
            metadata=metadata,
            connection=conn,
            **update_kwargs,
        )
        if not row:
            return None

        msg_row = None
        if assistant_message:
            msg_row = chat_message_repo.append_chat_message(
                public_thread_id=public_thread_id,
                workspace_id=workspace_id,
                role="assistant",
                content=assistant_message,
                payload={
                    "source": "graph_interrupt",
                    "status": "waiting_user_input",
                },
                created_by=user_id,
                generation_job_id=str(row["id"]),
                event_type="waiting_user_input",
                connection=conn,
            )
        else:
            msg_row = chat_message_repo.append_generation_job_chat_event(
                public_thread_id=public_thread_id,
                workspace_id=workspace_id,
                generation_job_id=str(row["id"]),
                event_type="waiting_user_input",
                role="system",
                content=None,
                payload={"job_id": job_id, "status": "waiting_user_input"},
                created_by=user_id,
                connection=conn,
            )

        # Snapshot
        latest_snapshot = state_service.get_latest_thread_state_snapshot(
            public_thread_id=public_thread_id,
            workspace_id=workspace_id,
            connection=conn,
        )

        state_service.save_thread_state_snapshot(
            public_thread_id=public_thread_id,
            workspace_id=workspace_id,
            snapshot_kind="waiting_user_input",
            state_payload=result_state,
            changed_fields=changed_fields,
            generation_job_id=str(row["id"]),
            source_message_id=str(msg_row["id"]) if msg_row else None,
            parent_snapshot_id=latest_snapshot.snapshot_id if latest_snapshot else None,
            snapshot_key=f"{job_id}:waiting",
            created_by=user_id,
            connection=conn,
        )

    return _job_response_from_db_row(row)


def _create_output_records_for_done_job_db(
    row: dict,
    result_payload: dict,
    final_path: str | None,
    connection: object,
    include_usage_payload: bool = False,
):
    if not final_path or not row.get("workspace_id") or not row.get("thread_id") or not row.get("id"):
        return (None, row, None) if include_usage_payload else (None, row)

    effective_result_payload = dict(result_payload or {})
    asset = None
    r2_usage_payload = None
    if _should_attempt_r2_upload():
        _record_generation_job_event_db(
            row,
            "r2_upload_started",
            payload={"final_path": final_path, "upload_required": storage_settings.is_r2_upload_required()},
            connection=connection,
        )
        try:
            asset, effective_result_payload, row, r2_usage_payload = _upload_final_asset_to_r2(
                row,
                effective_result_payload,
                final_path,
                connection=connection,
            )
            if storage_settings.is_r2_upload_required() and not _has_browser_result_url(effective_result_payload):
                raise AssetStorageError("R2 upload completed without a browser-usable result URL.")
            _record_generation_job_event_db(
                row,
                "r2_upload_completed",
                payload={
                    "bucket": asset.get("bucket"),
                    "object_key": asset.get("object_key"),
                    "url_mode": effective_result_payload.get("url_mode"),
                    "final_image_url_present": bool(effective_result_payload.get("final_image_url")),
                    "download_url_present": bool(effective_result_payload.get("download_url")),
                },
                connection=connection,
            )
        except AssetStorageError:
            _record_generation_job_event_db(
                row,
                "r2_upload_failed",
                payload={
                    "error_code": "r2_upload_failed",
                    "message": "R2 upload failed.",
                    "fallback": "local_dev",
                    "upload_required": storage_settings.is_r2_upload_required(),
                },
                connection=connection,
            )
            if storage_settings.is_r2_upload_required():
                raise
            asset = None
            effective_result_payload["final_image_url"] = None
            effective_result_payload["download_url"] = None
            row = generation_job_repo.update_generation_job_row(
                str(row["public_job_id"]),
                result_payload=effective_result_payload,
                metadata={**(row.get("metadata") or {}), "storage_warning": "r2_upload_failed_local_dev_fallback"},
                connection=connection,
            ) or row

    if asset is None:
        asset = asset_repo.create_asset(
            workspace_id=str(row["workspace_id"]),
            thread_id=str(row["thread_id"]),
            created_by=row.get("requested_by"),
            bucket="local-dev",
            object_key=final_path,
            kind="result",
            storage_provider="local_dev",
            metadata={
                "source": "generation_job_done",
                "serving_status": "not_public",
                "public_serving": False,
            },
            connection=connection,
        )

    if asset and asset.get("storage_provider") != "r2":
        effective_result_payload = merge_final_asset_into_result_payload(
            result_payload=effective_result_payload,
            asset_row=asset,
            storage_provider=asset.get("storage_provider") or "local_dev",
        )
        row = generation_job_repo.update_generation_job_row(
            str(row["public_job_id"]),
            result_payload=effective_result_payload,
            connection=connection,
        ) or row

    output = generation_output_repo.create_generation_output(
        workspace_id=str(row["workspace_id"]),
        thread_id=str(row["thread_id"]),
        job_id=str(row["id"]),
        asset_id=str(asset["id"]) if asset else None,
        variant_index=0,
        is_final=False,
        result_payload=effective_result_payload,
        metadata={"result_payload_summary": _result_payload_summary(effective_result_payload)},
        previous_output_id=str(row["previous_output_id"]) if row.get("previous_output_id") else None,
        connection=connection,
    )
    final_output = generation_output_repo.mark_output_final(str(output["id"]), workspace_id=str(row["workspace_id"]), connection=connection)
    
    archive_service.sync_archive_for_output(
        workspace_id=str(row["workspace_id"]),
        internal_output_id=str(output["id"]),
        connection=connection,
    )
    _record_generation_job_event_db(row, "archive_linked", payload={"public_output_id": output.get("public_output_id")}, connection=connection)

    if final_output:
        result = ({**output, **final_output}, row, r2_usage_payload)
        return result if include_usage_payload else result[:2]
    result = (output, row, r2_usage_payload)
    return result if include_usage_payload else result[:2]


def _upload_final_asset_to_r2(
    row: dict,
    result_payload: dict,
    final_path: str,
    connection: object,
) -> tuple[dict, dict, dict, dict | None]:
    workspace_id = str(row["workspace_id"])
    public_thread_id = _thread_public_or_internal(row)
    public_job_id = str(row["public_job_id"])
    filename = Path(final_path).name or "final_0.png"
    object_key = build_generation_object_key(
        workspace_id=workspace_id,
        thread_id=public_thread_id,
        job_id=public_job_id,
        filename=filename,
    )
    uploaded = upload_file_to_r2(
        local_path=final_path,
        object_key=object_key,
        metadata={
            "job_id": public_job_id,
            "workspace_id": workspace_id,
            "thread_id": public_thread_id,
            "asset_kind": "result",
        },
    )
    asset = asset_repo.create_asset(
        workspace_id=workspace_id,
        thread_id=str(row["thread_id"]),
        created_by=row.get("requested_by"),
        bucket=uploaded.bucket,
        object_key=uploaded.object_key,
        kind="result",
        storage_provider=uploaded.storage_provider,
        mime_type=uploaded.mime_type,
        size_bytes=uploaded.size_bytes,
        width=uploaded.width,
        height=uploaded.height,
        public_url=uploaded.public_url,
        signed_url_expires_at=uploaded.signed_url_expires_at,
        metadata=uploaded.metadata,
        connection=connection,
    )
    r2_usage_payload = _build_r2_usage_payload(row=row, uploaded_size_bytes=uploaded.size_bytes, asset_id=str(asset.get("id")) if asset else None)
    effective_result_payload = merge_final_asset_into_result_payload(
        result_payload=result_payload,
        asset_row=asset,
        uploaded_asset=uploaded,
        storage_provider=uploaded.storage_provider,
    )
    updated_row = generation_job_repo.update_generation_job_row(
        public_job_id,
        result_payload=effective_result_payload,
        connection=connection,
    ) or row
    return asset, effective_result_payload, updated_row, r2_usage_payload


def _build_r2_usage_payload(
    *,
    row: dict,
    uploaded_size_bytes: int | None,
    asset_id: str | None,
) -> dict | None:
    if not uploaded_size_bytes or uploaded_size_bytes <= 0 or not row.get("workspace_id"):
        return None
    public_job_id = str(row.get("public_job_id") or row.get("id") or "")
    return {
        "workspace_id": str(row["workspace_id"]),
        "quantity": uploaded_size_bytes,
        "created_by": row.get("requested_by"),
        "thread_id": str(row.get("thread_id")) if row.get("thread_id") else None,
        "job_id": str(row.get("id")) if row.get("id") else None,
        "provider": "cloudflare_r2",
        "plan": (row.get("metadata") or {}).get("user_plan"),
        "idempotency_key": f"r2_upload:{public_job_id}:{asset_id or 'unknown'}",
        "metadata": {
            "asset_id_present": bool(asset_id),
            "asset_kind": "result",
            "source": "generation_job_r2_upload",
            "size_bytes": uploaded_size_bytes,
        },
    }


def _record_r2_usage_for_uploaded_asset(
    *,
    row: dict,
    uploaded_size_bytes: int | None,
    asset_id: str | None,
    connection: object | None = None,
) -> None:
    payload = _build_r2_usage_payload(row=row, uploaded_size_bytes=uploaded_size_bytes, asset_id=asset_id)
    if payload:
        _safe_record_r2_usage(payload)


def _safe_record_r2_usage(payload: dict) -> None:
    try:
        usage_service.record_r2_upload_usage(**payload)
    except Exception:
        logger.warning("Failed to record generation R2 usage.", exc_info=True)


def _record_generation_job_event_db(
    row: dict,
    event_type: str,
    message: str | None = None,
    payload: dict | None = None,
    connection: object | None = None,
) -> dict | None:
    if not row.get("workspace_id") or not row.get("thread_id") or not row.get("id"):
        return None
    return generation_job_event_repo.record_generation_job_event(
        workspace_id=str(row["workspace_id"]),
        thread_id=str(row["thread_id"]),
        job_id=str(row["id"]),
        event_type=event_type,
        message=message,
        payload=payload or {},
        connection=connection,
    )


def _job_response_from_db_row(row: dict | None) -> GenerationJobResponse | None:
    if not row:
        return None
    metadata = sanitize_generation_job_metadata_for_api(row.get("metadata") or {})
    error = row.get("error")
    safe_result_payload = sanitize_result_artifact_payload_for_api(row.get("result_payload"))
    return GenerationJobResponse(
        job_id=str(row.get("public_job_id")),
        thread_id=row.get("public_thread_id") or metadata.get("public_thread_id"),
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
        source_asset_id=metadata.get("source_asset_id"),
        reference_asset_id=metadata.get("reference_asset_id"),
        output_path=normalize_repo_relative_artifact_path(row.get("output_path")),
        result_payload=safe_result_payload,
        error=ErrorResponse(**error) if isinstance(error, dict) and error.get("error_code") else None,
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


def _thread_public_or_internal(row: dict) -> str:
    metadata = row.get("metadata") or {}
    return str(row.get("public_thread_id") or metadata.get("public_thread_id") or row.get("thread_id"))


def _should_attempt_r2_upload() -> bool:
    return storage_settings.is_r2_upload_enabled()


def _has_browser_result_url(result_payload: dict | None) -> bool:
    if not result_payload:
        return False
    for key in ("final_image_url", "download_url", "preview_image_url", "copy_visual_preview_url"):
        value = result_payload.get(key)
        if not value:
            continue
        normalized = str(value).strip().lower()
        if normalized.startswith("http://") or normalized.startswith("https://"):
            return True
    return False


def _resolve_final_artifact_path(result_payload: dict, output_path: str | None) -> str | None:
    if output_path:
        return output_path
    for key in ("final_image_path", "download_path"):
        value = (result_payload or {}).get(key)
        if value:
            return str(value)
    return None


def _mark_generation_job_failed_from_row_db(
    row: dict,
    error: dict,
    metadata: dict,
    connection: object,
) -> GenerationJobResponse | None:
    error_payload = {
        "error_code": str(error.get("error_code") or "generation_job_execution_failed"),
        "error_type": error.get("error_type"),
        "message": str(error.get("message") or "Generation job execution failed."),
        "detail": error.get("detail"),
    }
    failed_row = generation_job_repo.mark_generation_job_failed_row(
        str(row["public_job_id"]),
        error_payload,
        metadata=metadata,
        connection=connection,
    )
    if not failed_row:
        return None
    _record_generation_job_event_db(
        failed_row,
        "failed",
        message=error_payload["message"],
        payload={
            "error_code": error_payload["error_code"],
            "error_type": error_payload.get("error_type"),
            "message": error_payload["message"],
        },
        connection=connection,
    )
    chat_thread_repo.fail_chat_thread_generation(
        public_thread_id=_thread_public_or_internal(failed_row),
        workspace_id=str(failed_row["workspace_id"]),
        expected_active_job_id=str(failed_row["id"]) if failed_row.get("id") else None,
        connection=connection,
    )
    return _job_response_from_db_row(failed_row)


def _result_payload_summary(result_payload: dict) -> dict:
    return {
        "schema_version": result_payload.get("schema_version"),
        "final_image_path": result_payload.get("final_image_path"),
        "final_image_url": result_payload.get("final_image_url"),
        "download_url": result_payload.get("download_url"),
        "engine": result_payload.get("engine"),
        "render_mode": result_payload.get("render_mode"),
    }


def _request_payload_summary(request: GenerationJobCreateRequest) -> dict:
    return {
        "entry_mode": request.entry_mode,
        "run_mode": request.run_mode,
        "ad_format": request.ad_format,
        "copy_generation_mode": request.copy_generation_mode,
        "selected_reference_template_id": request.selected_reference_template_id,
        "source_asset_id": request.source_asset_id,
        "reference_asset_id": request.reference_asset_id,
        "user_plan": request.user_plan,
        "user_input_preview": _preview_user_input(request.user_input),
        "metadata": _safe_request_metadata(request.metadata),
    }
