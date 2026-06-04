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
    source: str = "generated"
    created_at: str | None = None
    saved_at: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class ArchiveItemCreateRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    public_job_id: str | None = Field(default=None, max_length=120)
    thumbnail_url: str | None = None
    image_url: str | None = None
    status: Literal["saved", "favorite", "failed"] = "saved"
    ad_format: str | None = Field(default=None, max_length=80)
    platform: str | None = Field(default=None, max_length=80)
    source: Literal["generated", "reference_template", "uploaded"] = "generated"
    workspace_id: str | None = None
    user_id: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class ArchiveListResponse(BaseModel):
    success: Literal[True] = True
    items: list[ArchiveItemResponse]
    pagination: Pagination
    empty_state: EmptyState | None = None
    meta: ApiMeta = Field(default_factory=ApiMeta)


class ArchiveMutationResponse(BaseModel):
    success: Literal[True] = True
    item: ArchiveItemResponse
    meta: ApiMeta = Field(default_factory=ApiMeta)
