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
        return ChatStateSnapshotResponse(**row)

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
                    return ChatStateSnapshotResponse(**s)

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
        return ChatStateSnapshotResponse(**snapshot)

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
        return ChatStateSnapshotResponse(**row) if row else None
        
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
        return ChatStateSnapshotResponse(**latest)

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
        return ChatStateSnapshotResponse(**row) if row else None
        
    with _SNAPSHOTS_MEM_LOCK:
        thread = chat_service.get_chat_thread(public_thread_id, user_id=user_id)
        if not thread:
            return None
        effective_user_id = getattr(thread, "user_id", user_id) or "default"
        store_key = f"{effective_user_id}:{public_thread_id}"
        for s in _SNAPSHOTS_MEM.get(store_key, []):
            if s.get("snapshot_key") == snapshot_key:
                return ChatStateSnapshotResponse(**s)
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
        return [ChatStateSnapshotResponse(**r) for r in rows], total
        
    with _SNAPSHOTS_MEM_LOCK:
        thread = chat_service.get_chat_thread(public_thread_id, user_id=user_id)
        if not thread:
            return [], 0
        effective_user_id = getattr(thread, "user_id", user_id) or "default"
        store_key = f"{effective_user_id}:{public_thread_id}"
        snapshots = sorted(_SNAPSHOTS_MEM.get(store_key, []), key=lambda s: s["snapshot_version"], reverse=True)
        page = snapshots[offset: offset + limit]
        return [ChatStateSnapshotResponse(**s) for s in page], len(snapshots)

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
        restored[k] = v
        
    # 3. Always overwrite user_input
    restored["user_input"] = user_input
    
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
                workspace = workspace_repo.ensure_demo_workspace(
                    user_id=user_id or db_settings.get_demo_user_id(),
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
