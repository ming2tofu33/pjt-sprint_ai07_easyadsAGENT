"""Chat thread service: memory/postgres 분기."""

from __future__ import annotations

from datetime import datetime, timezone
from threading import RLock
from uuid import UUID
from uuid import uuid4

from orchestrator.app.api.schemas.chat_threads import (
    ChatMessageCreateRequest,
    ChatMessageResponse,
    ChatThreadCreateRequest,
    ChatThreadResponse,
    ChatThreadUpdateRequest,
)
from orchestrator.app.db import settings as db_settings
from orchestrator.app.db.repositories import chat_messages as chat_message_repo
from orchestrator.app.db.repositories import chat_threads as chat_thread_repo
from orchestrator.app.db.repositories import workspaces as workspace_repo
from orchestrator.app.db.session import db_transaction
from orchestrator.app.chat_threads.errors import (
    ChatThreadArchivedError,
    ChatThreadHasActiveJobError,
    ChatThreadLimitReachedError,
)
from orchestrator.app.chat_threads.sanitization import sanitize_chat_payload

# ---------------------------------------------------------------------------
# 상수
# ---------------------------------------------------------------------------

_BLOCKED_BRIEF_KEYS = {
    "api_key",
    "openai_api_key",
    "hf_token",
    "huggingface_token",
    "token",
    "authorization",
    "password",
    "secret",
    "service_role_key",
    "database_url",
    "chain_of_thought",
    "raw_llm_response",
    "raw_prompt",
}

# ---------------------------------------------------------------------------
# Memory store
# ---------------------------------------------------------------------------

_CHAT_THREADS: dict[str, dict] = {}  # public_thread_id -> internal dict
_CHAT_MESSAGES: dict[str, list[dict]] = {}  # public_thread_id -> [msg, ...]
_STORE_LOCK = RLock()


def reset_chat_thread_store_for_tests() -> None:
    with _STORE_LOCK:
        _CHAT_THREADS.clear()
        _CHAT_MESSAGES.clear()


# ---------------------------------------------------------------------------
# 헬퍼
# ---------------------------------------------------------------------------


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _iso(value) -> str:
    if value is None:
        return _now_iso()
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return str(value)


def _use_postgres() -> bool:
    return db_settings.get_db_backend() == "postgres"


def _db_uuid_or_none(value: str | None) -> str | None:
    if not value:
        return None
    try:
        return str(UUID(str(value)))
    except (TypeError, ValueError):
        return None




def _sanitize_brief(value) -> dict | list | str | object:
    return sanitize_chat_payload(value)


def _sanitize_message_payload(value):
    return sanitize_chat_payload(value)


def _effective_user_id(user_id: str | None) -> str | None:
    return user_id or db_settings.get_demo_user_id()


def _authenticated_user_id(user_id: str | None) -> str | None:
    normalized = (user_id or "").strip()
    return normalized or None


def _ensure_workspace_for_user(user_id: str | None, connection: object | None = None) -> dict:
    authenticated_user_id = _authenticated_user_id(user_id)
    if authenticated_user_id:
        return workspace_repo.ensure_user_workspace(user_id=authenticated_user_id, connection=connection)
    return workspace_repo.ensure_demo_workspace(user_id=_effective_user_id(user_id), connection=connection)


def _owner_matches(data: dict, user_id: str | None) -> bool:
    effective = _effective_user_id(user_id)
    return data.get("_owner_user_id") == effective


def _thread_row_to_response(row: dict) -> ChatThreadResponse:
    """DB row → ChatThreadResponse. active_job_id는 public job id로 변환."""
    active_job_id = row.get("active_public_job_id") or None
    # active_public_job_id join 컬럼이 없는 경우 fallback (내부 UUID 미노출 처리)
    if active_job_id and not str(active_job_id).startswith("job_"):
        active_job_id = None

    return ChatThreadResponse(
        thread_id=str(row["public_thread_id"]),
        title=row.get("title"),
        status=row.get("status") or "draft",
        brand_kit_id=str(row["brand_kit_id"]) if row.get("brand_kit_id") else None,
        project_id=str(row["project_id"]) if row.get("project_id") else None,
        final_brief=sanitize_chat_payload(row.get("final_brief") or {}),
        active_job_id=str(active_job_id) if active_job_id else None,
        has_final_output=row.get("final_output_id") is not None,
        last_message_at=_iso(row.get("last_message_at")),
        archived_at=_iso(row["archived_at"]) if row.get("archived_at") else None,
        created_at=_iso(row.get("created_at")),
        updated_at=_iso(row.get("updated_at")),
    )


def _msg_row_to_response(row: dict, public_thread_id: str) -> ChatMessageResponse:
    """DB row → ChatMessageResponse. message_id는 msg_ prefix."""
    raw_id = str(row.get("id") or "")
    message_id = f"msg_{raw_id.replace('-', '')}" if raw_id else f"msg_{uuid4().hex}"

    raw_public_job_id = row.get("public_job_id") or row.get("job_id")
    job_id = str(raw_public_job_id) if raw_public_job_id and str(raw_public_job_id).startswith("job_") else None

    return ChatMessageResponse(
        message_id=message_id,
        thread_id=public_thread_id,
        sequence_no=int(row.get("sequence_no") or 0),
        role=row.get("role") or "user",
        content=row.get("content"),
        payload=sanitize_chat_payload(row.get("payload") or {}),
        created_by=row.get("created_by"),
        job_id=job_id,
        event_type=row.get("event_type"),
        created_at=_iso(row.get("created_at")),
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def create_chat_thread(request: ChatThreadCreateRequest) -> ChatThreadResponse:
    if _use_postgres():
        return _create_chat_thread_db(request)
    return _create_chat_thread_memory(request)


def get_chat_thread(thread_id: str, user_id: str | None = None) -> ChatThreadResponse | None:
    if _use_postgres():
        return _get_chat_thread_db(thread_id, user_id=user_id)
    return _get_chat_thread_memory(thread_id, user_id=user_id)


def list_chat_threads(
    user_id: str | None = None,
    include_archived: bool = False,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[ChatThreadResponse], int]:
    """(threads, total) 반환."""
    if _use_postgres():
        return _list_chat_threads_db(user_id=user_id, include_archived=include_archived, limit=limit, offset=offset)
    return _list_chat_threads_memory(user_id=user_id, include_archived=include_archived, limit=limit, offset=offset)


def update_chat_thread(
    thread_id: str,
    request: ChatThreadUpdateRequest,
    user_id: str | None = None,
) -> ChatThreadResponse | None:
    if _use_postgres():
        return _update_chat_thread_db(thread_id, request, user_id=user_id)
    return _update_chat_thread_memory(thread_id, request, user_id=user_id)


def archive_chat_thread(thread_id: str, user_id: str | None = None) -> ChatThreadResponse | None:
    if _use_postgres():
        return _archive_chat_thread_db(thread_id, user_id=user_id)
    return _archive_chat_thread_memory(thread_id, user_id=user_id)


def append_chat_message(
    thread_id: str,
    request: ChatMessageCreateRequest,
    user_id: str | None = None,
) -> ChatMessageResponse | None:
    if _use_postgres():
        return _append_chat_message_db(thread_id, request, user_id=user_id)
    return _append_chat_message_memory(thread_id, request, user_id=user_id)


def list_chat_messages(
    thread_id: str,
    user_id: str | None = None,
    limit: int = 100,
    offset: int = 0,
) -> tuple[list[ChatMessageResponse], int]:
    """(messages, total) 반환."""
    if _use_postgres():
        return _list_chat_messages_db(thread_id, user_id=user_id, limit=limit, offset=offset)
    return _list_chat_messages_memory(thread_id, user_id=user_id, limit=limit, offset=offset)


def set_thread_active_job(
    public_thread_id: str,
    internal_job_id: str,
    public_job_id: str,
    status: str = "generating",
) -> None:
    """GenerationJob service에서 호출: active_job_id 설정."""
    if _use_postgres():
        chat_thread_repo.set_chat_thread_active_job(public_thread_id, internal_job_id, status=status)
    else:
        _set_active_job_memory(public_thread_id, public_job_id, status=status)


def set_thread_final_output(
    public_thread_id: str,
    internal_output_id: str,
    final_brief: dict | None = None,
    expected_public_job_id: str | None = None,
) -> None:
    """GenerationJob service에서 호출: final_output_id 설정."""
    if _use_postgres():
        chat_thread_repo.set_chat_thread_final_output(
            public_thread_id, internal_output_id, final_brief=final_brief
        )
    else:
        _set_final_output_memory(
            public_thread_id,
            has_output=True,
            final_brief=final_brief,
            expected_public_job_id=expected_public_job_id,
        )


def clear_thread_active_job(
    public_thread_id: str,
    status: str,
    expected_public_job_id: str | None = None,
) -> bool:
    """GenerationJob service에서 호출: active_job_id clear."""
    if _use_postgres():
        row = chat_thread_repo.clear_chat_thread_active_job(
            public_thread_id,
            status=status,
            expected_active_job_id=expected_public_job_id,
        )
        return row is not None
    else:
        return _clear_active_job_memory(
            public_thread_id,
            status=status,
            expected_public_job_id=expected_public_job_id,
        )


# ---------------------------------------------------------------------------
# Memory backend 구현
# ---------------------------------------------------------------------------


def _create_chat_thread_memory(request: ChatThreadCreateRequest) -> ChatThreadResponse:
    with _STORE_LOCK:
        # Mirror the postgres per-workspace guard: cap non-archived threads per owner.
        max_threads = db_settings.get_max_threads_per_workspace()
        existing = sum(
            1
            for t in _CHAT_THREADS.values()
            if _owner_matches(t, request.user_id) and not t.get("archived_at")
        )
        if existing >= max_threads:
            raise ChatThreadLimitReachedError(
                f"Workspace already has the maximum of {max_threads} active chat threads."
            )
        now = _now_iso()
        tid = f"thread_{uuid4().hex}"
        thread = ChatThreadResponse(
            thread_id=tid,
            title=request.title,
            status="draft",
            brand_kit_id=request.brand_kit_id,
            project_id=request.project_id,
            final_brief=_sanitize_brief(request.final_brief) if request.final_brief else {},
            active_job_id=None,
            has_final_output=False,
            last_message_at=now,
            archived_at=None,
            created_at=now,
            updated_at=now,
        )
        data = thread.model_dump(mode="json")
        data["_owner_user_id"] = _effective_user_id(request.user_id)
        _CHAT_THREADS[tid] = data
        _CHAT_MESSAGES[tid] = []
        return thread




















# ---------------------------------------------------------------------------
# Postgres backend 구현
# ---------------------------------------------------------------------------


def _get_chat_thread_memory(thread_id: str, user_id: str | None = None) -> ChatThreadResponse | None:
    with _STORE_LOCK:
        data = _CHAT_THREADS.get(thread_id)
        if not data or not _owner_matches(data, user_id):
            return None
        return ChatThreadResponse(**data)


def _list_chat_threads_memory(user_id: str | None = None, include_archived: bool = False, limit: int = 50, offset: int = 0) -> tuple[list[ChatThreadResponse], int]:
    with _STORE_LOCK:
        items = [t for t in _CHAT_THREADS.values() if _owner_matches(t, user_id)]
        if not include_archived:
            items = [t for t in items if not t.get("archived_at")]
        items.sort(key=lambda t: t.get("last_message_at") or "", reverse=True)
        page = items[offset: offset + limit]
        return [ChatThreadResponse(**t) for t in page], len(items)


def _update_chat_thread_memory(thread_id: str, request: ChatThreadUpdateRequest, user_id: str | None = None) -> ChatThreadResponse | None:
    with _STORE_LOCK:
        data = _CHAT_THREADS.get(thread_id)
        if not data or not _owner_matches(data, user_id):
            return None
        if data.get("archived_at"):
            raise ChatThreadArchivedError()
        updated = dict(data)
        set_fields = request.model_fields_set
        if "title" in set_fields:
            updated["title"] = request.title
        if "brand_kit_id" in set_fields:
            updated["brand_kit_id"] = request.brand_kit_id
        if "project_id" in set_fields:
            updated["project_id"] = request.project_id
        if "final_brief" in set_fields:
            updated["final_brief"] = _sanitize_brief(request.final_brief or {})
        updated["updated_at"] = _now_iso()
        _CHAT_THREADS[thread_id] = updated
        return ChatThreadResponse(**updated)


def _archive_chat_thread_memory(thread_id: str, user_id: str | None = None) -> ChatThreadResponse | None:
    with _STORE_LOCK:
        data = _CHAT_THREADS.get(thread_id)
        if not data or not _owner_matches(data, user_id):
            return None
        if data.get("archived_at"):
            return ChatThreadResponse(**data)
        if data.get("active_job_id"):
            raise ChatThreadHasActiveJobError()
        now = _now_iso()
        updated = {**data, "status": "archived", "archived_at": now, "active_job_id": None, "updated_at": now}
        _CHAT_THREADS[thread_id] = updated
        return ChatThreadResponse(**updated)


def _append_chat_message_memory(thread_id: str, request: ChatMessageCreateRequest, user_id: str | None = None) -> ChatMessageResponse | None:
    with _STORE_LOCK:
        data = _CHAT_THREADS.get(thread_id)
        if not data or not _owner_matches(data, user_id):
            return None
        if data.get("archived_at"):
            raise ChatThreadArchivedError()
        msgs = _CHAT_MESSAGES.setdefault(thread_id, [])
        now = _now_iso()
        msg = ChatMessageResponse(
            message_id=f"msg_{uuid4().hex}",
            thread_id=thread_id,
            sequence_no=(msgs[-1]["sequence_no"] + 1) if msgs else 1,
            role=request.role,
            content=request.content,
            payload=_sanitize_message_payload(request.payload),
            created_by=_effective_user_id(user_id),
            created_at=now,
        )
        msgs.append(msg.model_dump(mode="json"))
        if request.role == "user" and data.get("status") in {"completed", "failed"}:
            data = {**data, "status": "draft"}
        _CHAT_THREADS[thread_id] = {**data, "last_message_at": now, "updated_at": now}
        return msg


def _list_chat_messages_memory(thread_id: str, user_id: str | None = None, limit: int = 100, offset: int = 0) -> tuple[list[ChatMessageResponse], int]:
    with _STORE_LOCK:
        data = _CHAT_THREADS.get(thread_id)
        if not data or not _owner_matches(data, user_id):
            return [], 0
        msgs = _CHAT_MESSAGES.get(thread_id, [])
        page = msgs[offset: offset + limit]
        return [ChatMessageResponse(**m) for m in page], len(msgs)


def _set_active_job_memory(public_thread_id: str, public_job_id: str, status: str = "generating") -> None:
    with _STORE_LOCK:
        data = _CHAT_THREADS.get(public_thread_id)
        if not data:
            return
        if data.get("archived_at"):
            raise ChatThreadArchivedError()
        if data.get("active_job_id"):
            raise ChatThreadHasActiveJobError()
        _CHAT_THREADS[public_thread_id] = {**data, "active_job_id": public_job_id, "status": status, "updated_at": _now_iso()}


def _set_final_output_memory(
    public_thread_id: str,
    has_output: bool,
    final_brief: dict | None = None,
    expected_public_job_id: str | None = None,
) -> None:
    with _STORE_LOCK:
        data = _CHAT_THREADS.get(public_thread_id)
        if data:
            if expected_public_job_id is not None and data.get("active_job_id") != expected_public_job_id:
                return
            updated = {**data, "has_final_output": has_output, "updated_at": _now_iso()}
            if final_brief is not None:
                updated["final_brief"] = _sanitize_brief(final_brief)
            _CHAT_THREADS[public_thread_id] = updated


def _clear_active_job_memory(
    public_thread_id: str,
    status: str,
    expected_public_job_id: str | None = None,
) -> bool:
    with _STORE_LOCK:
        data = _CHAT_THREADS.get(public_thread_id)
        if data:
            if expected_public_job_id is not None and data.get("active_job_id") != expected_public_job_id:
                return False
            _CHAT_THREADS[public_thread_id] = {**data, "active_job_id": None, "status": status, "updated_at": _now_iso()}
            return True
        return False

def append_generation_job_chat_event_memory(
    *,
    thread_id: str,
    job_id: str,
    event_type: str,
    role: str,
    content: str | None,
    payload: dict,
    user_id: str | None,
) -> ChatMessageResponse | None:
    with _STORE_LOCK:
        data = _CHAT_THREADS.get(thread_id)
        if not data or not _owner_matches(data, user_id):
            return None
        if data.get("archived_at"):
            raise ChatThreadArchivedError()
        msgs = _CHAT_MESSAGES.setdefault(thread_id, [])
        now = _now_iso()

        # Dedupe check
        for m in reversed(msgs):
            if m.get("job_id") == job_id and m.get("event_type") == event_type:
                return ChatMessageResponse(**m)

        msg = ChatMessageResponse(
            message_id=f"msg_{uuid4().hex}",
            thread_id=thread_id,
            sequence_no=(msgs[-1]["sequence_no"] + 1) if msgs else 1,
            role=role,
            content=content,
            payload=_sanitize_message_payload(payload),
            created_by=_effective_user_id(user_id),
            job_id=job_id,
            event_type=event_type,
            created_at=now,
        )
        msgs.append(msg.model_dump(mode="json"))
        if role == "user" and data.get("status") in {"completed", "failed"}:
            data = {**data, "status": "draft"}
        _CHAT_THREADS[thread_id] = {**data, "last_message_at": now, "updated_at": now}
        return msg




def _create_chat_thread_db(request: ChatThreadCreateRequest) -> ChatThreadResponse:
    user_id = request.user_id or db_settings.get_demo_user_id()
    with db_transaction() as conn:
        ws = _ensure_workspace_for_user(request.user_id, connection=conn)
        row = chat_thread_repo.create_chat_thread(
            workspace_id=str(ws["id"]),
            created_by=user_id,
            title=request.title,
            brand_kit_id=_db_uuid_or_none(request.brand_kit_id),
            project_id=_db_uuid_or_none(request.project_id),
            final_brief=_sanitize_brief(request.final_brief) if request.final_brief else {},
            connection=conn,
        )
    return _thread_row_to_response(row)














def _get_demo_workspace(user_id: str | None = None) -> dict:
    with db_transaction() as conn:
        return _ensure_workspace_for_user(user_id, connection=conn)


def _get_demo_workspace_id(user_id: str | None = None) -> str:
    return str(_get_demo_workspace(user_id)["id"])


def _get_chat_thread_db(thread_id: str, user_id: str | None = None) -> ChatThreadResponse | None:
    workspace_id = _get_demo_workspace_id(user_id)
    row = chat_thread_repo.get_chat_thread_by_public_id(thread_id, workspace_id=workspace_id)
    return _thread_row_to_response(row) if row else None


def get_chat_thread_with_workspace(
    thread_id: str,
    user_id: str | None = None,
) -> tuple[ChatThreadResponse, str] | None:
    if not _use_postgres():
        thread = get_chat_thread(thread_id, user_id=user_id)
        return (thread, "memory_workspace") if thread else None

    workspace_id = _get_demo_workspace_id(user_id)
    row = chat_thread_repo.get_chat_thread_by_public_id(thread_id, workspace_id=workspace_id)

    if not row and user_id is None:
        row = chat_thread_repo.get_chat_thread_by_public_id(thread_id, workspace_id=None)

    if not row:
        return None

    return _thread_row_to_response(row), str(row["workspace_id"])


def _list_chat_threads_db(user_id: str | None = None, include_archived: bool = False, limit: int = 50, offset: int = 0) -> tuple[list[ChatThreadResponse], int]:
    workspace_id = _get_demo_workspace_id(user_id)
    rows = chat_thread_repo.list_chat_threads(
        workspace_id=workspace_id,
        include_archived=include_archived,
        limit=limit,
        offset=offset,
    )
    total = chat_thread_repo.count_chat_threads(workspace_id=workspace_id, include_archived=include_archived)
    return [_thread_row_to_response(r) for r in rows], total


def _update_chat_thread_db(thread_id: str, request: ChatThreadUpdateRequest, user_id: str | None = None) -> ChatThreadResponse | None:
    workspace_id = _get_demo_workspace_id(user_id)
    existing = chat_thread_repo.get_chat_thread_by_public_id(thread_id, workspace_id=workspace_id)
    if not existing:
        return None
    if existing.get("archived_at"):
        raise ChatThreadArchivedError()
    kwargs: dict = {}
    set_fields = request.model_fields_set
    if "title" in set_fields:
        kwargs["title"] = request.title
    if "brand_kit_id" in set_fields:
        kwargs["brand_kit_id"] = _db_uuid_or_none(request.brand_kit_id)
    if "project_id" in set_fields:
        kwargs["project_id"] = _db_uuid_or_none(request.project_id)
    if "final_brief" in set_fields:
        kwargs["final_brief"] = _sanitize_brief(request.final_brief or {})
    if kwargs:
        row = chat_thread_repo.update_chat_thread(thread_id, workspace_id=workspace_id, **kwargs)
        if not row:
            return None
    row = chat_thread_repo.get_chat_thread_by_public_id(thread_id, workspace_id=workspace_id) or existing
    return _thread_row_to_response(row)


def _archive_chat_thread_db(thread_id: str, user_id: str | None = None) -> ChatThreadResponse | None:
    workspace_id = _get_demo_workspace_id(user_id)
    existing = chat_thread_repo.get_chat_thread_by_public_id(thread_id, workspace_id=workspace_id)
    if not existing:
        return None
    if existing.get("archived_at"):
        return _thread_row_to_response(existing)
    if existing.get("active_job_id"):
        raise ChatThreadHasActiveJobError()
    row = chat_thread_repo.archive_chat_thread(thread_id, workspace_id=workspace_id)
    return _thread_row_to_response(row) if row else None


def _append_chat_message_db(thread_id: str, request: ChatMessageCreateRequest, user_id: str | None = None) -> ChatMessageResponse | None:
    workspace_id = _get_demo_workspace_id(user_id)
    existing = chat_thread_repo.get_chat_thread_by_public_id(thread_id, workspace_id=workspace_id)
    if not existing:
        return None
    if existing.get("archived_at"):
        raise ChatThreadArchivedError()
    row = chat_message_repo.append_chat_message(
        public_thread_id=thread_id,
        workspace_id=workspace_id,
        role=request.role,
        content=request.content,
        payload=_sanitize_message_payload(request.payload),
        created_by=_effective_user_id(user_id),
    )
    return _msg_row_to_response(row, thread_id)


def _list_chat_messages_db(thread_id: str, user_id: str | None = None, limit: int = 100, offset: int = 0) -> tuple[list[ChatMessageResponse], int]:
    workspace_id = _get_demo_workspace_id(user_id)
    rows = chat_message_repo.list_chat_messages(thread_id, workspace_id=workspace_id, limit=limit, offset=offset)
    total = chat_message_repo.count_chat_messages(thread_id, workspace_id=workspace_id)
    return [_msg_row_to_response(r, thread_id) for r in rows], total
