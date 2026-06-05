"""Generation Output API DTOs."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from orchestrator.app.api.schemas.common import ApiMeta, EmptyState, Pagination


class GenerationOutputResponse(BaseModel):
    output_id: str
    thread_id: str | None = None
    job_id: str | None = None
    variant_index: int = 0
    output_type: str = "final_image"
    is_final: bool = False
    image_url: str | None = None
    thumbnail_url: str | None = None
    download_url: str | None = None
    mime_type: str | None = None
    width: int | None = None
    height: int | None = None
    storage_provider: str | None = None
    result_payload: dict[str, Any] = Field(default_factory=dict)
    created_at: str | None = None
    updated_at: str | None = None


class GenerationOutputListResponse(BaseModel):
    success: bool = True
    items: list[GenerationOutputResponse]
    pagination: Pagination
    empty_state: EmptyState | None = None
    meta: ApiMeta = Field(default_factory=ApiMeta)
