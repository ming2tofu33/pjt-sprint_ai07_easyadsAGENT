"""Generation job API DTOs."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from orchestrator.app.api.schemas.common import ApiMeta, ErrorResponse


GenerationJobStatus = Literal[
    "queued",
    "running",
    "done",
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
GenerationRunMode = Literal[
    "queued_only",
    "mock_immediate",
    "graph_immediate",
    "gpt_image_2_actual",
    "gpt_image_2_smoke",
    "sd35_local",
    "sd35_local_smoke",
    "sd35_large_real",
    "flux_local",
    "flux_local_smoke",
    "flux_schnell_real",
    "flux",
    "flux_smoke",
]
ResultArtifactPayloadDict = dict[str, Any]


class GenerationJobCreateRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    user_id: str | None = Field(default=None, alias="userId")
    thread_id: str | None = Field(default=None, alias="threadId")
    brand_kit_id: str | None = Field(default=None, alias="brandKitId")
    entry_mode: str = Field(default="chat_start", alias="entryMode")
    user_input: str = Field(alias="userInput")
    selected_reference_template_id: str | None = Field(default=None, alias="selectedReferenceTemplateId")
    source_image_path: str | None = Field(default=None, alias="sourceImagePath")
    reference_image_path: str | None = Field(default=None, alias="referenceImagePath")
    copy_generation_mode: str | None = Field(default=None, alias="copyGenerationMode")
    selected_copy_id: str | None = Field(default=None, alias="selectedCopyId")
    selected_channel_id: str | None = Field(default=None, alias="selectedChannelId")
    selected_tone: str | None = Field(default=None, alias="selectedTone")
    custom_direction: str | None = Field(default=None, alias="customDirection")
    user_custom_headline: str | None = Field(default=None, alias="userCustomHeadline")
    user_custom_subcopy: str | None = Field(default=None, alias="userCustomSubcopy")
    user_plan: str = Field(default="free", alias="userPlan")
    ad_format: str | None = Field(default=None, alias="adFormat")
    run_mode: GenerationRunMode = Field(default="queued_only", alias="runMode")
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("user_input")
    @classmethod
    def user_input_not_empty(cls, value: str) -> str:
        if not value or not value.strip():
            raise ValueError("user_input must not be empty")
        return value.strip()

    @field_validator("thread_id", mode="before")
    @classmethod
    def normalize_thread_id(cls, v: str | None) -> str | None:
        if v is None:
            return None
        normalized = str(v).strip()
        if not normalized:
            return None
        if not normalized.startswith("thread_"):
            raise ValueError("thread_id must start with 'thread_'")
        return normalized


class GenerationJobAnswerRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    field: str | None = None
    value: str | None = None
    custom_text: str | None = Field(default=None, alias="customText")
    selected_copy_id: str | None = Field(default=None, alias="selectedCopyId")
    user_custom_headline: str | None = Field(default=None, alias="userCustomHeadline")
    user_custom_subcopy: str | None = Field(default=None, alias="userCustomSubcopy")
    payload: dict[str, Any] = Field(default_factory=dict)

    def to_resume_payload(self, *, job_id: str, thread_id: str) -> dict[str, Any]:
        resume_payload: dict[str, Any] = {
            "job_id": job_id,
            "thread_id": thread_id,
        }
        if self.field is not None:
            resume_payload["field"] = self.field
        if self.value is not None:
            resume_payload["value"] = self.value
        if self.custom_text:
            resume_payload["custom_text"] = self.custom_text
        if self.selected_copy_id:
            resume_payload["selected_copy_id"] = self.selected_copy_id
        if self.user_custom_headline:
            resume_payload["user_custom_headline"] = self.user_custom_headline
        if self.user_custom_subcopy:
            resume_payload["user_custom_subcopy"] = self.user_custom_subcopy
        resume_payload.update(self.payload)
        return resume_payload


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
    # Kept as a dict for backward-compatible API responses. The payload is
    # validated/sanitized by orchestrator.app.artifacts before response output.
    result_payload: ResultArtifactPayloadDict | None = None
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
