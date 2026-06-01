"""Structured API error helpers."""

from __future__ import annotations

from fastapi import HTTPException

from orchestrator.app.api.schemas.common import ErrorResponse, RecoveryAction


def raise_api_error(
    status_code: int,
    error_code: str,
    message: str,
    detail: str | None = None,
    recovery_actions: list[RecoveryAction] | None = None,
) -> None:
    error = ErrorResponse(
        error_code=error_code,
        message=message,
        detail=detail,
        recovery_actions=recovery_actions or [],
    )
    raise HTTPException(
        status_code=status_code,
        detail=error.model_dump(mode="json"),
    )
