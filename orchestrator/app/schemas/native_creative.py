"""Schemas for GPT Image 2 native typography single-shot lane."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class CreativeExecutionPlan(BaseModel):
    schema_version: Literal["creative_execution_plan_v1"] = "creative_execution_plan_v1"
    image_engine: Literal["gpt_image_2", "flux2_klein_4b", "sd35_large"]
    execution_lane: Literal["gpt_native_single_shot", "local_visual_first", "manual_review"]
    copy_authoring_mode: Literal["none", "gpt_structured"]
    text_rendering_mode: Literal["none", "native_typography", "external_renderer"]
    copy_precision: Literal["none", "semantic", "exact"]
    max_text_blocks: int = Field(ge=0, le=2)
    native_text_allowed: bool
    image_call_limit: Literal[1] = 1
    automatic_edit_allowed: Literal[False] = False
    automatic_retry_allowed: Literal[False] = False
    external_renderer_fallback_allowed: Literal[False] = False
    reason_codes: list[str] = Field(default_factory=list)


class NativeTypographyEligibilityDecision(BaseModel):
    eligible: bool
    recommended_lane: Literal["gpt_native_single_shot", "gpt_image_only_single_shot", "local_visual_first", "manual_review"]
    reason_codes: list[str] = Field(default_factory=list)
    blocking_reasons: list[str] = Field(default_factory=list)
    max_text_blocks: int = Field(ge=0, le=2)
    max_total_characters: int = Field(ge=0, le=80)
    confidence: float = Field(ge=0.0, le=1.0)


class ApprovedNativeCopyBrief(BaseModel):
    schema_version: Literal["approved_native_copy_brief_v1"] = "approved_native_copy_brief_v1"
    headline: str | None = None
    supporting_copy: str | None = None
    closing_copy: str | None = None
    action_cta: str | None = None
    language: Literal["korean", "english", "mixed"]
    message_role: Literal["image_only", "headline_only", "headline_plus_support", "headline_plus_closing"]
    exact_text_required: Literal[True] = True
    allowed_texts: list[str] = Field(default_factory=list)
    forbidden_texts: list[str] = Field(default_factory=list)
    max_text_blocks: int = Field(ge=0, le=2)
    max_total_characters: int = Field(ge=0, le=80)
    verified_evidence_ids: list[str] = Field(default_factory=list)
    unsupported_claim_categories: list[str] = Field(default_factory=list)
    compliance_status: Literal["approved", "manual_review", "rejected"]
    rejection_reasons: list[str] = Field(default_factory=list)


class NativeSourceVisualAnalysis(BaseModel):
    product_bbox: list[float] | None = None
    preferred_text_zone: str | None = None
    negative_space_regions: list[str] = Field(default_factory=list)
    dominant_colors: list[str] = Field(default_factory=list)
    package_native_text: list[str] = Field(default_factory=list)
    external_overlay_text: list[str] = Field(default_factory=list)
    source_suitable: bool = True
    manual_review_required: bool = False
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)


class NativeCreativePromptPackage(BaseModel):
    schema_version: Literal["native_creative_prompt_v1"] = "native_creative_prompt_v1"
    product_description: str
    campaign_objective: str
    composition_direction: str
    visual_style: str
    lighting_direction: str
    color_direction: str
    typography_direction: str
    product_zone: str
    text_zone: str
    approved_copy: ApprovedNativeCopyBrief
    required_elements: list[str] = Field(default_factory=list)
    forbidden_elements: list[str] = Field(default_factory=list)
    exact_allowed_texts: list[str] = Field(default_factory=list)
    exact_forbidden_texts: list[str] = Field(default_factory=list)
    final_prompt: str
    prompt_sha256: str
    image_model: Literal["gpt-image-2"] = "gpt-image-2"
    image_call_limit: Literal[1] = 1
    automatic_edit_allowed: Literal[False] = False
    automatic_retry_allowed: Literal[False] = False
    preflight_status: Literal["approved", "manual_review", "rejected"]


class NativeCreativePreflightReview(BaseModel):
    decision: Literal["approved", "revision_required", "manual_review", "rejected"]
    copy_grounded: bool
    claims_supported: bool
    language_natural: bool
    generic_cta_absent: bool
    text_budget_valid: bool
    native_typography_suitable: bool
    product_visual_direction_valid: bool
    failure_reasons: list[str] = Field(default_factory=list)
    revision_instructions: list[str] = Field(default_factory=list)


class NativeGenerationBudget(BaseModel):
    max_image_calls: Literal[1] = 1
    image_calls_reserved: int = 0
    image_calls_started: int = 0
    image_calls_completed: int = 0
    allow_edit_retry: Literal[False] = False
    allow_generation_retry: Literal[False] = False
    allow_external_renderer: Literal[False] = False
    request_fingerprint: str
    status: Literal["not_started", "reserved", "in_flight", "completed", "failed", "uncertain"] = "not_started"


class NativeGenerationReview(BaseModel):
    expected_texts: list[str] = Field(default_factory=list)
    detected_texts: list[str] = Field(default_factory=list)
    exact_text_match_score: float = Field(ge=0.0, le=1.0)
    unexpected_text_detected: bool
    missing_text_detected: bool
    product_match_score: float = Field(ge=0.0, le=1.0)
    product_obstruction_score: float = Field(ge=0.0, le=1.0)
    hierarchy_score: float = Field(ge=0.0, le=1.0)
    typography_quality_score: float = Field(ge=0.0, le=1.0)
    composition_score: float = Field(ge=0.0, le=1.0)
    commercial_viability_score: float = Field(ge=0.0, le=1.0)
    decision: Literal["accept", "manual_review", "reject"]
    failure_reasons: list[str] = Field(default_factory=list)
