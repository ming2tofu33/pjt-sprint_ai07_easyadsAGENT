"""Generation job API DTOs."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator

from orchestrator.app.api.schemas.common import ApiMeta, ErrorResponse


GenerationJobStatus = Literal[
    "queued",
    "briefing",
    "waiting_user_input",
    "planning",
    "t2i_running",
    "validating",
    "rendering",
    "completed",
    "failed",
    "cancelled",
]
GenerationRunMode = Literal["queued_only", "mock_immediate"]


class GenerationJobCreateRequest(BaseModel):
    user_id: str | None = None
    brand_kit_id: str | None = None
    entry_mode: str = "chat_start"
    user_input: str
    selected_reference_template_id: str | None = None
    source_image_path: str | None = None
    reference_image_path: str | None = None
    copy_generation_mode: str | None = None
    user_plan: str = "free"
    ad_format: str | None = None
    run_mode: GenerationRunMode = "queued_only"
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("user_input")
    @classmethod
    def user_input_not_empty(cls, value: str) -> str:
        if not value or not value.strip():
            raise ValueError("user_input must not be empty")
        return value.strip()


class GenerationProgress(BaseModel):
    progress_percent: int = Field(default=0, ge=0, le=100)
    current_stage: str = "queued"
    estimated_seconds_remaining: int | None = Field(default=None, ge=0)
    stage_order: list[str] = Field(default_factory=list)


class GenerationJobResponse(BaseModel):
    job_id: str
    thread_id: str | None = None
    user_id: str | None = None
    brand_kit_id: str | None = None
    status: GenerationJobStatus
    progress: GenerationProgress
    selected_reference_template_id: str | None = None
    output_path: str | None = None
    result_payload: dict[str, Any] | None = None
    error: ErrorResponse | None = None
    created_at: str
    updated_at: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class GenerationJobCreateResponse(BaseModel):
    success: Literal[True] = True
    job: GenerationJobResponse
    meta: ApiMeta = Field(default_factory=ApiMeta)


class GenerationJobGetResponse(BaseModel):
    success: Literal[True] = True
    job: GenerationJobResponse
    meta: ApiMeta = Field(default_factory=ApiMeta)
