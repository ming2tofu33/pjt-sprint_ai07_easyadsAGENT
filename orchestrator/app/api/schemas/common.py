"""Common backend API response DTOs."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class ApiMeta(BaseModel):
    request_id: str | None = None
    timestamp: str | None = None
    version: str = "v1"


class RecoveryAction(BaseModel):
    action: str
    label: str
    href: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class ErrorResponse(BaseModel):
    success: Literal[False] = False
    error_code: str
    message: str
    detail: str | None = None
    recovery_actions: list[RecoveryAction] = Field(default_factory=list)
    meta: ApiMeta = Field(default_factory=ApiMeta)


class Pagination(BaseModel):
    limit: int = Field(..., ge=1)
    offset: int = Field(..., ge=0)
    total: int = Field(..., ge=0)
    has_more: bool


class EmptyState(BaseModel):
    kind: str
    title: str
    message: str
    suggested_actions: list[RecoveryAction] = Field(default_factory=list)


class AssetRef(BaseModel):
    asset_id: str
    asset_type: str
    url: str | None = None
    path: str | None = None
    thumbnail_url: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
