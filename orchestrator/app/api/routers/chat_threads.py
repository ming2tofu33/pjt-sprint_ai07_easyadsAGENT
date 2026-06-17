"""Chat thread API routes."""

from __future__ import annotations

from fastapi import APIRouter, Body, Query, status

from orchestrator.app.api.errors import raise_api_error
from orchestrator.app.api.schemas.chat_threads import (
    ChatMessageCreateRequest,
    ChatMessageCreateResponse,
    ChatMessageListResponse,
    ChatThreadCreateRequest,
    ChatThreadCreateResponse,
    ChatThreadGetResponse,
    ChatThreadListResponse,
    ChatThreadArchiveRequest,
    ChatThreadResumeStateGetResponse,
    ChatThreadResumeStateResponse,
    ChatThreadRestoreRequest,
    ChatThreadUpdateRequest,
    ChatThreadStateGetResponse,
)
from orchestrator.app.chat_threads.errors import ChatThreadServiceError
from orchestrator.app.chat_threads import service as chat_service
from orchestrator.app.chat_threads import state_service

router = APIRouter()


# ---------------------------------------------------------------------------
# 에러 헬퍼
# ---------------------------------------------------------------------------


def _not_found(thread_id: str) -> None:
    raise_api_error(
        status_code=404,
        error_code="chat_thread_not_found",
        message="Chat thread was not found.",
        detail=f"thread_id={thread_id}",
    )


def _archived(thread_id: str) -> None:
    raise_api_error(
        status_code=409,
        error_code="chat_thread_archived",
        message="Chat thread is archived.",
        detail=f"thread_id={thread_id}",
    )


def _has_active_job(thread_id: str) -> None:
    raise_api_error(
        status_code=409,
        error_code="chat_thread_has_active_job",
        message="Chat thread already has an active generation job.",
        detail=f"thread_id={thread_id}",
    )


def _handle_service_error(exc: ChatThreadServiceError, thread_id: str) -> None:
    if exc.error_code == "chat_thread_archived":
        _archived(thread_id)
        return
    if exc.error_code == "chat_thread_has_active_job":
        _has_active_job(thread_id)
        return
    if exc.error_code == "chat_thread_has_pending_job":
        raise_api_error(
            status_code=409,
            error_code=exc.error_code,
            message=exc.message,
            detail=f"thread_id={thread_id}",
        )
        return
    if exc.error_code == "chat_thread_not_found":
        _not_found(thread_id)
        return
    raise_api_error(
        status_code=400,
        error_code=exc.error_code,
        message=exc.message,
        detail=f"thread_id={thread_id}",
    )


def _user_scope_kwargs(user_id: str | None, account_type: str | None) -> dict:
    kwargs = {"user_id": user_id}
    if account_type:
        kwargs["account_type"] = account_type
    return kwargs


# ---------------------------------------------------------------------------
# Thread endpoints
# ---------------------------------------------------------------------------


@router.post(
    "/chat-threads",
    response_model=ChatThreadCreateResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_chat_thread_route(request: ChatThreadCreateRequest) -> ChatThreadCreateResponse:
    try:
        thread = chat_service.create_chat_thread(request)
    except ChatThreadServiceError as exc:
        status_code = 409 if exc.error_code == "thread_limit_reached" else 400
        raise_api_error(
            status_code=status_code,
            error_code=exc.error_code,
            message=exc.message,
        )
    return ChatThreadCreateResponse(thread=thread)


@router.get(
    "/chat-threads",
    response_model=ChatThreadListResponse,
)
def list_chat_threads_route(
    user_id: str | None = Query(default=None, alias="userId"),
    account_type: str | None = Query(default=None, alias="accountType"),
    include_archived: bool = Query(default=False),
    include_total: bool = Query(default=True),
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> ChatThreadListResponse:
    threads, total = chat_service.list_chat_threads(
        include_archived=include_archived,
        include_total=include_total,
        limit=limit,
        offset=offset,
        **_user_scope_kwargs(user_id, account_type),
    )
    return ChatThreadListResponse(threads=threads, total=total)


@router.get(
    "/chat-threads/{thread_id}",
    response_model=ChatThreadGetResponse,
)
def get_chat_thread_route(
    thread_id: str,
    user_id: str | None = Query(default=None, alias="userId"),
    account_type: str | None = Query(default=None, alias="accountType"),
) -> ChatThreadGetResponse:
    thread = chat_service.get_chat_thread(thread_id, **_user_scope_kwargs(user_id, account_type))
    if not thread:
        _not_found(thread_id)
    return ChatThreadGetResponse(thread=thread)


@router.patch(
    "/chat-threads/{thread_id}",
    response_model=ChatThreadGetResponse,
)
def update_chat_thread_route(
    thread_id: str,
    request: ChatThreadUpdateRequest,
    user_id: str | None = Query(default=None, alias="userId"),
    account_type: str | None = Query(default=None, alias="accountType"),
) -> ChatThreadGetResponse:
    try:
        thread = chat_service.update_chat_thread(thread_id, request, **_user_scope_kwargs(user_id, account_type))
    except ChatThreadServiceError as exc:
        _handle_service_error(exc, thread_id)
        return  # type: ignore[return-value]
    if not thread:
        _not_found(thread_id)
    return ChatThreadGetResponse(thread=thread)


@router.post(
    "/chat-threads/{thread_id}/archive",
    response_model=ChatThreadGetResponse,
)
def archive_chat_thread_route(
    thread_id: str,
    request: ChatThreadArchiveRequest = Body(default_factory=ChatThreadArchiveRequest),
    user_id: str | None = Query(default=None, alias="userId"),
    account_type: str | None = Query(default=None, alias="accountType"),
) -> ChatThreadGetResponse:
    try:
        thread = chat_service.archive_chat_thread(
            thread_id,
            force=request.force,
            **_user_scope_kwargs(user_id, account_type),
        )
    except ChatThreadServiceError as exc:
        _handle_service_error(exc, thread_id)
        return  # type: ignore[return-value]
    if not thread:
        _not_found(thread_id)
    return ChatThreadGetResponse(thread=thread)


@router.post(
    "/chat-threads/{thread_id}/restore",
    response_model=ChatThreadGetResponse,
)
def restore_chat_thread_route(
    thread_id: str,
    request: ChatThreadRestoreRequest = Body(default_factory=ChatThreadRestoreRequest),
    user_id: str | None = Query(default=None, alias="userId"),
    account_type: str | None = Query(default=None, alias="accountType"),
) -> ChatThreadGetResponse:
    try:
        thread = chat_service.restore_chat_thread(
            thread_id,
            **_user_scope_kwargs(user_id, account_type),
        )
    except ChatThreadServiceError as exc:
        _handle_service_error(exc, thread_id)
        return  # type: ignore[return-value]
    if not thread:
        _not_found(thread_id)
    return ChatThreadGetResponse(thread=thread)


@router.get(
    "/chat-threads/{thread_id}/resume-state",
    response_model=ChatThreadResumeStateGetResponse,
)
def get_chat_thread_resume_state_route(
    thread_id: str,
    user_id: str | None = Query(default=None, alias="userId"),
    account_type: str | None = Query(default=None, alias="accountType"),
) -> ChatThreadResumeStateGetResponse:
    resume_state = chat_service.get_chat_thread_resume_state(
        thread_id,
        **_user_scope_kwargs(user_id, account_type),
    )
    if not resume_state:
        _not_found(thread_id)
    return ChatThreadResumeStateGetResponse(
        resume_state=ChatThreadResumeStateResponse.model_validate(
            resume_state,
            from_attributes=True,
        )
    )


@router.get(
    "/chat-threads/{thread_id}/state",
    response_model=ChatThreadStateGetResponse,
)
def get_chat_thread_state_route(
    thread_id: str,
    user_id: str | None = Query(default=None, alias="userId"),
    account_type: str | None = Query(default=None, alias="accountType"),
) -> ChatThreadStateGetResponse:
    resolved = chat_service.get_chat_thread_with_workspace(thread_id, **_user_scope_kwargs(user_id, account_type))
    if not resolved:
        _not_found(thread_id)

    _thread, workspace_id = resolved
    snapshot = state_service.get_latest_thread_state_snapshot(
        public_thread_id=thread_id,
        workspace_id=workspace_id,
        user_id=user_id,
    )
    return ChatThreadStateGetResponse(snapshot=snapshot)


# ---------------------------------------------------------------------------
# Message endpoints
# ---------------------------------------------------------------------------


@router.post(
    "/chat-threads/{thread_id}/messages",
    response_model=ChatMessageCreateResponse,
    status_code=status.HTTP_201_CREATED,
)
def append_message_route(
    thread_id: str,
    request: ChatMessageCreateRequest,
    user_id: str | None = Query(default=None, alias="userId"),
    account_type: str | None = Query(default=None, alias="accountType"),
) -> ChatMessageCreateResponse:
    try:
        msg = chat_service.append_chat_message(thread_id, request, **_user_scope_kwargs(user_id, account_type))
    except ChatThreadServiceError as exc:
        _handle_service_error(exc, thread_id)
        return  # type: ignore[return-value]
    if not msg:
        _not_found(thread_id)
    return ChatMessageCreateResponse(message=msg)


@router.get(
    "/chat-threads/{thread_id}/messages",
    response_model=ChatMessageListResponse,
)
def list_messages_route(
    thread_id: str,
    user_id: str | None = Query(default=None, alias="userId"),
    account_type: str | None = Query(default=None, alias="accountType"),
    limit: int = Query(default=100, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> ChatMessageListResponse:
    thread = chat_service.get_chat_thread(thread_id, **_user_scope_kwargs(user_id, account_type))
    if not thread:
        _not_found(thread_id)
    messages, total = chat_service.list_chat_messages(
        thread_id,
        limit=limit,
        offset=offset,
        **_user_scope_kwargs(user_id, account_type),
    )
    return ChatMessageListResponse(messages=messages, total=total)
