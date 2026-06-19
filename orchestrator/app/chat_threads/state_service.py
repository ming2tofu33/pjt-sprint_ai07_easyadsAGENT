"""Chat state service."""

from __future__ import annotations

from typing import Any
import threading
from uuid import uuid4

from orchestrator.app.db import settings as db_settings
from orchestrator.app.chat_threads import service as chat_service
from orchestrator.app.db.repositories import chat_state_snapshots as snapshot_repo
from orchestrator.app.schemas.chat_state_snapshots import ChatStateSnapshotResponse
from orchestrator.app.chat_threads.state_snapshot import serialize_marketing_state_snapshot

_SNAPSHOTS_MEM_LOCK = threading.RLock()
_SNAPSHOTS_MEM: dict[str, list[dict]] = {}  # (user_id, thread_id) -> list of snapshots

def _now_iso() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat()

def _to_response(row: dict) -> ChatStateSnapshotResponse:
    data = dict(row)
    created_at = data.get("created_at")
    if hasattr(created_at, "isoformat"):
        data["created_at"] = created_at.isoformat()
    return ChatStateSnapshotResponse(**data)

def reset_chat_state_snapshot_store_for_tests() -> None:
    with _SNAPSHOTS_MEM_LOCK:
        _SNAPSHOTS_MEM.clear()

def save_thread_state_snapshot(
    *,
    public_thread_id: str,
    workspace_id: str,
    snapshot_kind: str,
    state_payload: dict[str, Any],
    changed_fields: list[str],
    generation_job_id: str | None = None,
    source_message_id: str | None = None,
    parent_snapshot_id: str | None = None,
    selected_reference_template_id: str | None = None,
    reference_template_snapshot: dict | None = None,
    brand_kit_snapshot: dict | None = None,
    snapshot_key: str | None = None,
    metadata: dict | None = None,
    created_by: str | None = None,
    user_id: str | None = None,
    connection: object | None = None,
) -> ChatStateSnapshotResponse:
    from orchestrator.app.chat_threads.sanitization import sanitize_chat_payload
    safe_state_payload = serialize_marketing_state_snapshot(state_payload)
    safe_ref_snap = sanitize_chat_payload(reference_template_snapshot or {}) if reference_template_snapshot else None
    safe_brand_snap = sanitize_chat_payload(brand_kit_snapshot or {}) if brand_kit_snapshot else None
    safe_metadata = sanitize_chat_payload(metadata or {}) if metadata else None

    if db_settings.get_db_backend() == "postgres":
        public_snapshot_id = f"snapshot_{uuid4().hex}"
        row = snapshot_repo.create_chat_state_snapshot(
            public_snapshot_id=public_snapshot_id,
            public_thread_id=public_thread_id,
            workspace_id=workspace_id,
            snapshot_kind=snapshot_kind,
            state_payload=safe_state_payload,
            changed_fields=changed_fields,
            generation_job_id=generation_job_id,
            source_message_id=source_message_id,
            parent_snapshot_id=parent_snapshot_id,
            selected_reference_template_id=selected_reference_template_id,
            reference_template_snapshot=safe_ref_snap,
            brand_kit_snapshot=safe_brand_snap,
            snapshot_key=snapshot_key,
            metadata=safe_metadata,
            created_by=created_by,
            connection=connection,
        )
        return _to_response(row)

    with _SNAPSHOTS_MEM_LOCK:
        thread = chat_service.get_chat_thread(public_thread_id, user_id=user_id)
        if not thread:
            raise ValueError("Thread not found")

        effective_user_id = getattr(thread, "user_id", user_id) or "default"
        store_key = f"{effective_user_id}:{public_thread_id}"
        snapshots = _SNAPSHOTS_MEM.setdefault(store_key, [])
        
        # Idempotency check
        if snapshot_key:
            for s in snapshots:
                if s.get("snapshot_key") == snapshot_key:
                    return _to_response(s)

        next_version = max([s.get("snapshot_version", 0) for s in snapshots], default=0) + 1
        public_snapshot_id = f"snapshot_{uuid4().hex}"
        
        snapshot = {
            "snapshot_id": public_snapshot_id,
            "thread_id": public_thread_id,
            "job_id": generation_job_id, # Can't resolve internal job easily in memory, assume public id is passed
            "source_message_id": source_message_id,
            "parent_snapshot_id": parent_snapshot_id,
            "snapshot_version": next_version,
            "schema_version": 1,
            "snapshot_kind": snapshot_kind,
            "state_payload": safe_state_payload,
            "changed_fields": changed_fields,
            "selected_reference_template_id": selected_reference_template_id,
            "reference_template_snapshot": safe_ref_snap or {},
            "brand_kit_snapshot": safe_brand_snap or {},
            "snapshot_key": snapshot_key,
            "metadata": safe_metadata or {},
            "created_at": _now_iso()
        }
        snapshots.append(snapshot)
        return _to_response(snapshot)

def get_latest_thread_state_snapshot(
    public_thread_id: str,
    workspace_id: str,
    user_id: str | None = None,
    connection: object | None = None,
) -> ChatStateSnapshotResponse | None:
    if db_settings.get_db_backend() == "postgres":
        row = snapshot_repo.get_latest_chat_state_snapshot(
            public_thread_id=public_thread_id,
            workspace_id=workspace_id,
            connection=connection,
        )
        return _to_response(row) if row else None
        
    with _SNAPSHOTS_MEM_LOCK:
        thread = chat_service.get_chat_thread(public_thread_id, user_id=user_id)
        if not thread:
            return None
        effective_user_id = getattr(thread, "user_id", user_id) or "default"
        store_key = f"{effective_user_id}:{public_thread_id}"
        snapshots = _SNAPSHOTS_MEM.get(store_key, [])
        if not snapshots:
            return None
        latest = max(snapshots, key=lambda s: s["snapshot_version"])
        return _to_response(latest)

def get_chat_state_snapshot_by_key(
    snapshot_key: str,
    public_thread_id: str,
    workspace_id: str,
    user_id: str | None = None,
    connection: object | None = None,
) -> ChatStateSnapshotResponse | None:
    if db_settings.get_db_backend() == "postgres":
        row = snapshot_repo.get_chat_state_snapshot_by_key(
            snapshot_key=snapshot_key,
            thread_id=public_thread_id,
            workspace_id=workspace_id,
            connection=connection,
        )
        return _to_response(row) if row else None
        
    with _SNAPSHOTS_MEM_LOCK:
        thread = chat_service.get_chat_thread(public_thread_id, user_id=user_id)
        if not thread:
            return None
        effective_user_id = getattr(thread, "user_id", user_id) or "default"
        store_key = f"{effective_user_id}:{public_thread_id}"
        for s in _SNAPSHOTS_MEM.get(store_key, []):
            if s.get("snapshot_key") == snapshot_key:
                return _to_response(s)
        return None

def list_thread_state_snapshots(
    public_thread_id: str,
    workspace_id: str,
    limit: int = 100,
    offset: int = 0,
    user_id: str | None = None,
    connection: object | None = None,
) -> tuple[list[ChatStateSnapshotResponse], int]:
    if db_settings.get_db_backend() == "postgres":
        rows = snapshot_repo.list_chat_state_snapshots(
            public_thread_id=public_thread_id,
            workspace_id=workspace_id,
            limit=limit,
            offset=offset,
            connection=connection,
        )
        total = snapshot_repo.count_chat_state_snapshots(
            public_thread_id=public_thread_id,
            workspace_id=workspace_id,
            connection=connection,
        )
        return [_to_response(r) for r in rows], total
        
    with _SNAPSHOTS_MEM_LOCK:
        thread = chat_service.get_chat_thread(public_thread_id, user_id=user_id)
        if not thread:
            return [], 0
        effective_user_id = getattr(thread, "user_id", user_id) or "default"
        store_key = f"{effective_user_id}:{public_thread_id}"
        snapshots = sorted(_SNAPSHOTS_MEM.get(store_key, []), key=lambda s: s["snapshot_version"], reverse=True)
        page = snapshots[offset: offset + limit]
        return [_to_response(s) for s in page], len(snapshots)

def restore_thread_state(
    latest_snapshot: ChatStateSnapshotResponse | None,
    current_request_fields: dict[str, Any],
    user_input: str,
) -> dict[str, Any]:
    from orchestrator.app.chat_threads.state_snapshot import restore_persistent_state
    
    # 1. Restore persistent state
    restored = restore_persistent_state(latest_snapshot.state_payload if latest_snapshot else None)
    
    # 2. Merge explicit request fields (override)
    for k, v in current_request_fields.items():
        if k not in {"source_asset_id", "reference_asset_id"}:
            restored[k] = v
    from orchestrator.app.graph.state import overlay_current_request_asset_ids
    restored = overlay_current_request_asset_ids(
        restored,
        source_asset_id=current_request_fields.get("source_asset_id"),
        reference_asset_id=current_request_fields.get("reference_asset_id"),
    )
        
    # 3. Always overwrite user_input
    restored["user_input"] = user_input
    
    return restored


_NEW_GENERATION_TRANSIENT_KEYS = {
    "job_id",
    "missing_fields",
    "current_brief",
    "marketing_copy",
    "copy_candidates",
    "copy_candidate_origin",
    "progress_state",
    "quality_gate_decision",
    "quality_gate_status",
    "quality_gate_retry_feedback",
    "ocr_gate_decision",
    "ocr_gate_status",
    "ocr_gate_retry_feedback",
    "image_prompt_spec",
    "copy_spec",
    "copy_required",
    "text_layout_spec",
    "text_style_spec",
    "text_overlay_pending",
    "t2i_request",
    "t2i_result",
    "candidates",
    "artifact_refs",
    "background_validation_report",
    "safe_area_report",
    "readability_report",
    "render_result",
    "final_validation_report",
    "result_payload",
    "final_image_path",
    "error_message",
    "error_info",
    "selected_copy",
    "selected_copy_id",
    "selected_channel_id",
    "selected_tone",
    "custom_direction",
    "user_custom_headline",
    "user_custom_subcopy",
}

_NEW_GENERATION_TRANSIENT_CONTEXT_KEYS = {
    "__interrupt__",
    "current_question",
    "interrupt",
    "interrupts",
    "pending_field",
    "pending_fields",
    "pending_interrupt",
    "pending_option",
    "pending_options",
    "pending_question",
    "question",
    "resume_payload",
    "waiting_for",
}


def _strip_transient_context(context: Any) -> dict[str, Any] | None:
    if not isinstance(context, dict):
        return None
    stripped = {
        key: value
        for key, value in context.items()
        if str(key) not in _NEW_GENERATION_TRANSIENT_CONTEXT_KEYS
    }
    return stripped or None


def restore_thread_state_for_generation(
    latest_snapshot: ChatStateSnapshotResponse | None,
    current_request_fields: dict[str, Any],
    user_input: str,
    continuation_mode: str | None,
) -> dict[str, Any]:
    from orchestrator.app.chat_threads.state_snapshot import restore_persistent_state

    restored = restore_persistent_state(latest_snapshot.state_payload if latest_snapshot else None)

    if continuation_mode in {"new_turn", "retry_failed", "regenerate_from_output"}:
        for key in _NEW_GENERATION_TRANSIENT_KEYS:
            restored.pop(key, None)
        stripped_context = _strip_transient_context(restored.get("context"))
        if stripped_context:
            restored["context"] = stripped_context
        else:
            restored.pop("context", None)

    for k, v in current_request_fields.items():
        if k not in {"source_asset_id", "reference_asset_id"}:
            restored[k] = v
    from orchestrator.app.graph.state import overlay_current_request_asset_ids
    restored = overlay_current_request_asset_ids(
        restored,
        source_asset_id=current_request_fields.get("source_asset_id"),
        reference_asset_id=current_request_fields.get("reference_asset_id"),
    )

    restored["user_input"] = user_input
    restored["continuation_mode"] = continuation_mode

    return restored


def get_latest_thread_state_for_user(
    public_thread_id: str,
    user_id: str | None = None,
) -> ChatStateSnapshotResponse | None:
    # 1. Fetch thread to validate access
    thread = chat_service.get_chat_thread(public_thread_id, user_id=user_id)
    if not thread:
        return None
        
    raw_workspace_id = getattr(thread, "workspace_id", None)
    if raw_workspace_id:
        workspace_id = str(raw_workspace_id)
    else:
        if db_settings.get_db_backend() == "postgres":
            from orchestrator.app.db.repositories import workspaces as workspace_repo
            from orchestrator.app.db.session import db_transaction
            with db_transaction() as conn:
                if user_id and user_id.strip():
                    workspace = workspace_repo.ensure_user_workspace(user_id=user_id.strip(), connection=conn)
                else:
                    workspace = workspace_repo.ensure_demo_workspace(
                        user_id=db_settings.get_demo_user_id(),
                        connection=conn
                    )
                workspace_id = str(workspace["id"])
        else:
            workspace_id = "mem_workspace"
        
    return get_latest_thread_state_snapshot(
        public_thread_id=public_thread_id,
        workspace_id=workspace_id,
        user_id=user_id,
    )
