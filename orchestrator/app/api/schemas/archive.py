"""Archive API DTOs."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

from orchestrator.app.api.schemas.common import ApiMeta, EmptyState, Pagination


class ArchiveItemResponse(BaseModel):
    ad_id: str
    job_id: str | None = None
    title: str
    thumbnail_url: str | None = None
    image_url: str | None = None
    status: Literal["generating", "saved", "favorite", "failed"] = "saved"
    ad_format: str | None = None
    platform: str | None = None
    created_at: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class ArchiveListResponse(BaseModel):
    success: Literal[True] = True
    items: list[ArchiveItemResponse]
    pagination: Pagination
    empty_state: EmptyState | None = None
    meta: ApiMeta = Field(default_factory=ApiMeta)
