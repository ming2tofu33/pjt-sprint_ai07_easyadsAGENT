"""Schemas for validation feedback and regeneration."""

from __future__ import annotations

from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, Field


SCHEMA_VERSION = "validation_feedback_v1"


class ValidationFailureType(str, Enum):
    FAKE_TEXT = "fake_text"
    WATERMARK = "watermark"
    UNAUTHORIZED_LOGO = "unauthorized_logo"
    COPY_SAFE_AREA = "copy_safe_area"
    COPY_MISSING = "copy_missing"
    COPY_MALFORMED = "copy_malformed"
    COPY_UNREADABLE = "copy_unreadable"
    COPY_CLIPPING = "copy_clipping"
    UNEXPECTED_TEXT = "unexpected_text"
    VISUAL_CLUTTER = "visual_clutter"
    BUSINESS_FIT = "business_fit"
    COPY_CONTRAST = "copy_contrast"
    COMMERCIAL_VIABILITY = "commercial_viability"
    PROVIDER_UNAVAILABLE = "provider_unavailable"
    MANUAL_REVIEW_REQUIRED = "manual_review_required"


class SuggestedActionCode(str, Enum):
    INCREASE_COPY_SAFE_AREA = "increase_copy_safe_area"
    REMOVE_FAKE_TEXT = "remove_fake_text"
    REMOVE_WATERMARK = "remove_watermark"
    REDUCE_VISUAL_CLUTTER = "reduce_visual_clutter"
    IMPROVE_BUSINESS_FIT = "improve_business_fit"
    ADJUST_COPY_CONTRAST = "adjust_copy_contrast"
    ADJUST_COPY_LAYOUT = "adjust_copy_layout"
    RESTORE_MISSING_COPY = "restore_missing_copy"
    RERUN_WITH_PROMPT_V3_1 = "rerun_with_prompt_v3_1"
    MANUAL_REVIEW = "manual_review"


class SuggestedAction(BaseModel):
    code: SuggestedActionCode
    scope: Literal["image", "layout", "copy", "full", "manual"]
    priority: int = Field(ge=1, le=100)
    reason: str
    parameters: dict[str, Any] = Field(default_factory=dict)


class ValidationSummary(BaseModel):
    status: Literal["pass", "fail", "manual_review", "unavailable"]
    decision: Literal[
        "pass",
        "retry_image",
        "retry_layout",
        "retry_copy",
        "retry_full",
        "reject",
        "manual_review",
        "unavailable",
    ]
    overall_score: float | None = Field(default=None, ge=0, le=1)
    confidence: float | None = Field(default=None, ge=0, le=1)
    failure_types: list[ValidationFailureType]
    suggested_actions: list[SuggestedAction]
    source_summary: dict[str, Any]
    schema_version: str = SCHEMA_VERSION

    @property
    def retry_recommended(self) -> bool:
        return self.decision in {"retry_image", "retry_layout", "retry_copy", "retry_full"}

    @property
    def requires_manual_review(self) -> bool:
        return self.decision in {"manual_review", "unavailable"} or ValidationFailureType.MANUAL_REVIEW_REQUIRED in self.failure_types

