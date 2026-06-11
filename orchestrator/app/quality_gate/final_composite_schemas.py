"""Final composite quality loop schemas."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


CompositeFailureType = Literal[
    "expected_copy_mismatch",
    "unexpected_text",
    "generic_copy",
    "headline_too_long",
    "copy_clipping",
    "product_overlap",
    "face_hand_overlap",
    "weak_headline_hierarchy",
    "cta_dominance",
    "plate_too_large",
    "low_contrast",
    "visual_clutter",
    "alignment_error",
    "safe_margin_violation",
    "business_fit_mismatch",
    "brand_fit_mismatch",
    "commercial_viability_low",
    "font_fallback",
    "background_has_no_text_space",
    "provider_unavailable",
    "final_image_contract_mismatch",
]

CompositeRevisionAction = Literal[
    "none",
    "rewrite_copy",
    "shorten_copy",
    "retry_layout",
    "retry_text_style",
    "reduce_cta_emphasis",
    "regenerate_background",
    "manual_review",
    "reject",
]


class FinalCompositeMetricReport(BaseModel):
    expected_copy_match_score: float = Field(ge=0.0, le=1.0)
    clipping_detected: bool
    product_overlap_ratio: float = Field(ge=0.0)
    face_hand_overlap_ratio: float = Field(ge=0.0)
    headline_body_size_ratio: float = Field(ge=0.0)
    cta_headline_size_ratio: float = Field(ge=0.0)
    cta_area_ratio: float = Field(ge=0.0)
    plate_area_ratio: float = Field(ge=0.0)
    headline_contrast_ratio: float | None = None
    body_contrast_ratio: float | None = None
    cta_contrast_ratio: float | None = None
    safe_margin_pass: bool
    alignment_score: float | None = Field(default=None, ge=0.0, le=1.0)
    visual_clutter_score: float | None = Field(default=None, ge=0.0, le=1.0)
    business_fit_score: float | None = Field(default=None, ge=0.0, le=1.0)
    brand_fit_score: float | None = Field(default=None, ge=0.0, le=1.0)
    commercial_viability_score: float | None = Field(default=None, ge=0.0, le=1.0)


class FinalCompositeVLMResult(BaseModel):
    expected_copy_visible: bool = True
    copy_clipping_detected: bool = False
    product_overlap: bool = False
    face_hand_overlap: bool = False
    headline_hierarchy_score: float = Field(default=1.0, ge=0.0, le=1.0)
    cta_dominance_score: float = Field(default=1.0, ge=0.0, le=1.0)
    plate_excess_score: float = Field(default=1.0, ge=0.0, le=1.0)
    contrast_score: float = Field(default=1.0, ge=0.0, le=1.0)
    visual_clutter_score: float = Field(default=1.0, ge=0.0, le=1.0)
    alignment_score: float = Field(default=1.0, ge=0.0, le=1.0)
    safe_margin_score: float = Field(default=1.0, ge=0.0, le=1.0)
    business_fit_score: float = Field(default=1.0, ge=0.0, le=1.0)
    brand_fit_score: float = Field(default=1.0, ge=0.0, le=1.0)
    commercial_viability_score: float = Field(default=1.0, ge=0.0, le=1.0)
    generic_copy_detected: bool = False
    background_text_space_insufficient: bool = False
    failure_reasons: list[str] = Field(default_factory=list)
    suggested_action: CompositeRevisionAction = "none"
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)


class FinalCompositeQualityReport(BaseModel):
    status: Literal["pass", "revise", "manual_review", "reject", "unavailable"]
    evaluated_image_path: str
    evaluated_image_sha256: str
    deterministic_metrics: FinalCompositeMetricReport
    ocr_result: dict[str, Any] = Field(default_factory=dict)
    vlm_result: dict[str, Any] | None = None
    failure_types: list[CompositeFailureType] = Field(default_factory=list)
    primary_action: CompositeRevisionAction = "none"
    suggested_actions: list[CompositeRevisionAction] = Field(default_factory=list)
    retry_feedback: list[str] = Field(default_factory=list)
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    attempt: int = Field(default=1, ge=1)
    public_summary: dict[str, Any] = Field(default_factory=dict)


class CompositeRevisionPlan(BaseModel):
    action: CompositeRevisionAction
    rerun_from_node: str | None = None
    dirty_fields: list[str] = Field(default_factory=list)
    preserved_fields: list[str] = Field(default_factory=list)
    feedback: list[str] = Field(default_factory=list)
    budget_before: dict[str, int] = Field(default_factory=dict)
    budget_after: dict[str, int] = Field(default_factory=dict)
