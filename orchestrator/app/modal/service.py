"""Modal GenerationJob orchestration service."""

from __future__ import annotations

import base64
from pathlib import Path

from orchestrator.app.artifacts.service import ensure_job_output_dir
from orchestrator.app.db.repositories import generation_job_events as event_repo
from orchestrator.app.db.repositories import generation_jobs as job_repo
from orchestrator.app.db.repositories import usage_events as usage_repo
from orchestrator.app.modal.client import poll_modal_t2i_result, submit_modal_t2i_job
from orchestrator.app.modal.errors import ModalExecutionError, ModalResultError
from orchestrator.app.modal.schemas import ModalPollResult, ModalSubmitResult, ModalT2IRequest

MODAL_ELIGIBLE_RUN_MODES = {"sd35_local", "sd35_local_smoke", "flux_local", "flux_local_smoke", "flux", "flux_smoke"}


def is_modal_eligible_run_mode(run_mode: str | None) -> bool:
    return run_mode in MODAL_ELIGIBLE_RUN_MODES


def build_modal_t2i_request_from_job(
    *,
    job_row: dict,
    generation_request: object | None = None,
    t2i_request: dict | None = None,
) -> ModalT2IRequest:
    t2i_request = t2i_request or {}
    metadata = job_row.get("metadata") or {}
    public_job_id = str(job_row.get("public_job_id") or "")
    prompt = (
        t2i_request.get("prompt")
        or getattr(generation_request, "user_input", None)
        or job_row.get("prompt_text")
        or job_row.get("prompt_preview")
        or metadata.get("user_input_preview")
        or ""
    )
    run_mode = str(job_row.get("run_mode") or metadata.get("requested_run_mode") or "")
    engine = str(job_row.get("engine") or metadata.get("t2i_engine") or _engine_from_run_mode(run_mode) or "unknown")
    return ModalT2IRequest(
        job_id=public_job_id,
        thread_id=str(metadata.get("public_thread_id") or job_row.get("thread_id") or "") or None,
        workspace_id=str(job_row.get("workspace_id") or ""),
        run_mode=run_mode,
        engine=engine,
        prompt=str(prompt),
        negative_prompt=t2i_request.get("negative_prompt"),
        width=int(t2i_request.get("width") or 1024),
        height=int(t2i_request.get("height") or 1024),
        num_images=1,
        seed=t2i_request.get("seed"),
        model_name=job_row.get("model_name") or engine,
        model_version=job_row.get("model_version"),
        params=t2i_request.get("params") or {},
        metadata={
            "selected_reference_template_id": job_row.get("selected_reference_template_id"),
            "modal_result_transport": "inline_base64",
        },
    )


def submit_generation_job_to_modal(
    *,
    job_row: dict,
    modal_request: ModalT2IRequest,
    connection: object | None = None,
    client: object | None = None,
) -> ModalSubmitResult:
    _record_event(job_row, "modal_submit_started", payload={"engine": modal_request.engine}, connection=connection)
    try:
        submit_result = submit_modal_t2i_job(modal_request, client=client)
    except ModalExecutionError as exc:
        _record_event(
            job_row,
            "modal_submit_failed",
            payload={"error_code": "modal_submit_failed", "message": str(exc)},
            connection=connection,
        )
        raise
    metadata = {
        **(job_row.get("metadata") or {}),
        "modal_call_id_present": bool(submit_result.modal_call_id),
        "modal_provider": "modal",
        **submit_result.metadata,
    }
    updated = job_repo.attach_modal_call_id(
        str(job_row["public_job_id"]),
        submit_result.modal_call_id or "",
        metadata=metadata,
        connection=connection,
    )
    if updated:
        job_row.update(updated)
    job_repo.mark_generation_job_running_row(
        str(job_row["public_job_id"]),
        current_stage="modal_submitted",
        connection=connection,
    )
    _record_event(
        job_row,
        "modal_submitted",
        payload={"modal_call_id_present": bool(submit_result.modal_call_id), "status": submit_result.status},
        connection=connection,
    )
    return submit_result


def poll_and_process_modal_generation_job(*, job_id: str, client: object | None = None):
    from orchestrator.app.generation_jobs import service as generation_job_service

    job_row = job_repo.get_generation_job_row(job_id)
    if not job_row:
        return None
    modal_call_id = job_row.get("modal_call_id")
    if not modal_call_id:
        return generation_job_service.get_generation_job(job_id)
    poll_result = poll_modal_t2i_result(str(modal_call_id), client=client)
    if poll_result.status in {"pending", "running", "unknown"}:
        _record_event(job_row, "modal_poll", payload={"status": poll_result.status})
        if poll_result.status == "running":
            generation_job_service.mark_generation_job_running(job_id, "modal_running")
        return generation_job_service.get_generation_job(job_id)
    if poll_result.status in {"failed", "canceled"}:
        _record_event(job_row, "modal_failed", payload={"status": poll_result.status, "error": _safe_error(poll_result.error)})
        return generation_job_service.mark_generation_job_failed(
            job_id,
            {
                "error_code": "modal_generation_failed",
                "message": "Modal generation failed.",
                "detail": _safe_error(poll_result.error),
            },
        )
    if poll_result.status == "succeeded":
        _record_event(job_row, "modal_succeeded", payload={"modal_call_id_present": True})
        final_path = write_modal_result_image_to_output_dir(job_id=job_id, poll_result=poll_result)
        result_payload = {
            **poll_result.result_payload,
            "schema_version": poll_result.result_payload.get("schema_version") or "result_artifact_v1",
            "job_id": job_id,
            "final_image_path": final_path,
            "download_path": final_path,
            "engine": job_row.get("engine") or _engine_from_run_mode(job_row.get("run_mode")),
            "render_mode": "modal",
        }
        done = generation_job_service.mark_generation_job_done(job_id, result_payload=result_payload, output_path=final_path)
        _record_usage(job_row, poll_result)
        return done
    return generation_job_service.get_generation_job(job_id)


def write_modal_result_image_to_output_dir(*, job_id: str, poll_result: ModalPollResult) -> str:
    output_dir = ensure_job_output_dir(job_id)
    filename = Path(poll_result.filename or "final_0.png").name
    if not filename:
        filename = "final_0.png"
    target = output_dir / filename
    image_bytes = poll_result.image_bytes
    if image_bytes is None and poll_result.image_b64:
        image_bytes = base64.b64decode(poll_result.image_b64)
    if not image_bytes:
        raise ModalResultError("Modal succeeded without image bytes.")
    target.write_bytes(image_bytes)
    return target.as_posix()


def _record_event(row: dict, event_type: str, payload: dict | None = None, message: str | None = None, connection=None):
    if not row.get("workspace_id") or not row.get("thread_id") or not row.get("id"):
        return None
    return event_repo.record_generation_job_event(
        workspace_id=str(row["workspace_id"]),
        thread_id=str(row["thread_id"]),
        job_id=str(row["id"]),
        event_type=event_type,
        message=message,
        payload=payload or {},
        connection=connection,
    )


def _record_usage(row: dict, poll_result: ModalPollResult):
    usage = poll_result.usage or {}
    if not row.get("workspace_id") or not row.get("id"):
        return None
    return usage_repo.record_usage_event(
        workspace_id=str(row["workspace_id"]),
        thread_id=str(row.get("thread_id")) if row.get("thread_id") else None,
        job_id=str(row["id"]),
        event_type="modal_gpu_seconds",
        provider="modal",
        model_name=usage.get("model_name") or row.get("model_name"),
        plan=(row.get("metadata") or {}).get("user_plan"),
        quantity=usage.get("gpu_seconds"),
        unit="seconds",
        cost_usd=usage.get("cost_usd"),
        metadata={
            "modal_call_id_present": True,
            "gpu_type": usage.get("gpu_type"),
            "duration_ms": usage.get("duration_ms"),
        },
    )


def _engine_from_run_mode(run_mode: str | None) -> str | None:
    if run_mode in {"sd35_local", "sd35_local_smoke"}:
        return "sd35_large"
    if run_mode in {"flux_local", "flux_local_smoke", "flux", "flux_smoke"}:
        return "flux"
    return None


def _safe_error(error: dict | None) -> dict:
    if not error:
        return {}
    return {key: value for key, value in error.items() if str(key).lower() not in {"token", "secret", "api_key"}}
