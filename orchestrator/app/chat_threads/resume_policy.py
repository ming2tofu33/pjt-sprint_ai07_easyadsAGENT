"""Pure resume-action policy for generated chat threads."""

from __future__ import annotations

from typing import Any

from orchestrator.app.api.schemas.chat_threads import ChatThreadResumeStateResponse

_EXPLICIT_PENDING_MODES = {"new_turn", "retry_failed", "regenerate_from_output"}


def _get_value(source: Any, key: str, default: Any = None) -> Any:
    if source is None:
        return default
    if isinstance(source, dict):
        return source.get(key, default)
    return getattr(source, key, default)


def _public_id(value: Any, prefix: str) -> str | None:
    text = str(value) if value else None
    return text if text and text.startswith(prefix) else None


def _public_thread_id(thread: Any) -> str:
    return _public_id(_get_value(thread, "public_thread_id"), "thread_") or _public_id(
        _get_value(thread, "thread_id"), "thread_"
    ) or ""


def _snapshot_id(snapshot: Any) -> str | None:
    return _public_id(_get_value(snapshot, "snapshot_id"), "snapshot_")


def _snapshot_kind(snapshot: Any) -> str | None:
    value = _get_value(snapshot, "snapshot_kind")
    return str(value) if value else None


def _metadata(job: Any) -> dict[str, Any]:
    value = _get_value(job, "metadata") or {}
    return value if isinstance(value, dict) else {}


def _pending_question(job: Any) -> dict[str, Any] | None:
    metadata = _metadata(job)
    pending = metadata.get("pending_interrupt")
    if isinstance(pending, dict) and pending:
        return pending
    assistant_message = metadata.get("assistant_message")
    if isinstance(assistant_message, str) and assistant_message.strip():
        return {"message": assistant_message.strip()}
    return None


def _waiting_job_is_explicit_continuation(job: Any) -> bool:
    mode = _metadata(job).get("continuation_mode")
    return isinstance(mode, str) and mode in _EXPLICIT_PENDING_MODES


def compute_thread_resume_state(
    *,
    thread: Any,
    latest_snapshot: Any,
    waiting_job: Any,
) -> ChatThreadResumeStateResponse:
    """Return the single server-owned action for opening a generated thread."""

    thread_id = _public_thread_id(thread)
    active_job_id = _public_id(_get_value(thread, "active_public_job_id"), "job_") or _public_id(
        _get_value(thread, "active_job_id"), "job_"
    )
    final_job_id = _public_id(_get_value(thread, "final_public_job_id"), "job_")
    final_output_id = _public_id(_get_value(thread, "final_public_output_id"), "output_") or _public_id(
        _get_value(thread, "final_output_id"), "output_"
    )
    waiting_job_id = _public_id(_get_value(waiting_job, "public_job_id"), "job_") or _public_id(
        _get_value(waiting_job, "job_id"), "job_"
    )
    snapshot_id = _snapshot_id(latest_snapshot)
    snapshot_kind = _snapshot_kind(latest_snapshot)
    status = str(_get_value(thread, "status") or "draft")

    if active_job_id:
        return ChatThreadResumeStateResponse(
            action="locked_running",
            thread_id=thread_id,
            resume_job_id=active_job_id,
            final_output_id=final_output_id,
            latest_snapshot_id=snapshot_id,
            snapshot_kind=snapshot_kind,
            reason="thread_has_active_job",
        )

    if final_output_id and not (waiting_job_id and _waiting_job_is_explicit_continuation(waiting_job)):
        return ChatThreadResumeStateResponse(
            action="view_result",
            thread_id=thread_id,
            resume_job_id=final_job_id,
            final_output_id=final_output_id,
            latest_snapshot_id=snapshot_id,
            snapshot_kind=snapshot_kind,
            reason="thread_has_final_output",
        )

    if waiting_job_id:
        return ChatThreadResumeStateResponse(
            action="answer_pending_job",
            thread_id=thread_id,
            resume_job_id=waiting_job_id,
            final_output_id=final_output_id,
            latest_snapshot_id=snapshot_id,
            snapshot_kind=snapshot_kind,
            reason="thread_has_waiting_job",
            current_question=_pending_question(waiting_job),
        )

    if status == "failed" or snapshot_kind == "job_failed":
        reason = "latest_snapshot_failed" if snapshot_kind == "job_failed" else "thread_status_failed"
        return ChatThreadResumeStateResponse(
            action="retry_failed_job",
            thread_id=thread_id,
            resume_job_id=None,
            final_output_id=final_output_id,
            latest_snapshot_id=snapshot_id,
            snapshot_kind=snapshot_kind,
            reason=reason,
        )

    return ChatThreadResumeStateResponse(
        action="continue_draft",
        thread_id=thread_id,
        resume_job_id=None,
        final_output_id=final_output_id,
        latest_snapshot_id=snapshot_id,
        snapshot_kind=snapshot_kind,
        reason="thread_is_draft",
    )
