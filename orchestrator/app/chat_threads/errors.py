"""Typed chat thread service errors."""

from __future__ import annotations


class ChatThreadServiceError(Exception):
    def __init__(self, error_code: str, message: str) -> None:
        super().__init__(message)
        self.error_code = error_code
        self.message = message


class ChatThreadNotFoundError(ChatThreadServiceError):
    def __init__(self, message: str = "Chat thread was not found.") -> None:
        super().__init__("chat_thread_not_found", message)


class ChatThreadArchivedError(ChatThreadServiceError):
    def __init__(self, message: str = "Chat thread is archived.") -> None:
        super().__init__("chat_thread_archived", message)


class ChatThreadHasActiveJobError(ChatThreadServiceError):
    def __init__(self, message: str = "Chat thread already has an active generation job.") -> None:
        super().__init__("chat_thread_has_active_job", message)


class ChatThreadHasPendingJobError(ChatThreadServiceError):
    def __init__(self, message: str = "Chat thread has a generation job waiting for user input.") -> None:
        super().__init__("chat_thread_has_pending_job", message)


class ChatThreadRequiresContinuationModeError(ChatThreadServiceError):
    def __init__(self, message: str = "Chat thread requires continuationMode.") -> None:
        super().__init__("chat_thread_requires_continuation_mode", message)


class InvalidChatThreadRequestError(ChatThreadServiceError):
    def __init__(self, message: str = "Invalid chat thread request.") -> None:
        super().__init__("invalid_chat_thread_request", message)


class ChatThreadLimitReachedError(ChatThreadServiceError):
    def __init__(self, message: str = "Chat thread limit reached for this workspace.") -> None:
        super().__init__("thread_limit_reached", message)
