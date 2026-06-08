"""Validation feedback API DTOs."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from orchestrator.app.api.schemas.common import ApiMeta
from orchestrator.app.validation_feedback.schemas import SuggestedAction, SuggestedActionCode


class ValidationDetail(BaseModel):
    report_id: str | None = Field(default=None, alias="reportId")
    output_id: str | None = Field(default=None, alias="outputId")
    job_id: str | None = Field(default=None, alias="jobId")
    status: str
    decision: str
    overall_score: float | None = Field(default=None, alias="overallScore")
    confidence: float | None = None
    failure_types: list[str] = Field(default_factory=list, alias="failureTypes")
    suggested_actions: list[SuggestedAction] = Field(default_factory=list, alias="suggestedActions")
    retry_recommended: bool = Field(default=False, alias="retryRecommended")
    requires_manual_review: bool = Field(default=False, alias="requiresManualReview")
    schema_version: str = Field(default="validation_feedback_v1", alias="schemaVersion")
    created_at: str | None = Field(default=None, alias="createdAt")

    model_config = ConfigDict(populate_by_name=True)


class ValidationDetailResponse(BaseModel):
    success: bool = True
    validation: ValidationDetail
    meta: ApiMeta = Field(default_factory=ApiMeta)


class RegenerateOutputRequest(BaseModel):
    suggested_actions: list[SuggestedActionCode] = Field(default_factory=list, alias="suggestedActions", max_length=10)
    scope: Literal["image", "layout", "copy", "full"] | None = None
    user_instruction: str | None = Field(default=None, alias="userInstruction", max_length=500)
    idempotency_key: str = Field(alias="idempotencyKey", min_length=8, max_length=128)

    model_config = ConfigDict(populate_by_name=True)


class RegenerationDetail(BaseModel):
    job_id: str = Field(alias="jobId")
    thread_id: str | None = Field(default=None, alias="threadId")
    parent_job_id: str | None = Field(default=None, alias="parentJobId")
    previous_output_id: str | None = Field(default=None, alias="previousOutputId")
    depth: int
    status: str
    applied_actions: list[str] = Field(default_factory=list, alias="appliedActions")
    idempotent_replay: bool = Field(default=False, alias="idempotentReplay")

    model_config = ConfigDict(populate_by_name=True)


class RegenerateOutputResponse(BaseModel):
    success: bool = True
    regeneration: RegenerationDetail
    meta: ApiMeta = Field(default_factory=ApiMeta)

