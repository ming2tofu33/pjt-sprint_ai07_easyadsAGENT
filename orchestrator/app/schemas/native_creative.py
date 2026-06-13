"""Schemas for GPT Image 2 native typography single-shot lane."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from orchestrator.app.schemas.input_evidence import EvidenceItem


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
    copy_source_mode: Literal["generated", "user_exact"] = "generated"
    source_user_request: str | None = None
    non_display_instructions: list[str] = Field(default_factory=list)
    product_identity: str | None = None
    desired_positioning: list[str] = Field(default_factory=list)
    campaign_intent: str | None = None
    transformation_performed: bool = False
    product_evidence_ids: list[str] = Field(default_factory=list)
    creative_direction_evidence_ids: list[str] = Field(default_factory=list)
    copy_claim_evidence_ids: list[str] = Field(default_factory=list)
    provider_metadata: dict = Field(default_factory=dict)
    selected_candidate_id: str | None = None
    positioning_realization_plan: dict = Field(default_factory=dict)
    candidate_scorecard: dict = Field(default_factory=dict)
    alternative_candidate_summaries: list[dict] = Field(default_factory=list)


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


PositioningChannel = Literal["product_copy", "sensory_copy", "context_copy", "visual_style", "composition", "lighting", "color", "typography", "negative_space"]


class PositioningRealizationPlan(BaseModel):
    requested_positioning: list[str] = Field(default_factory=list)
    realization_mode: Literal["implicit", "balanced", "explicit"] = "implicit"
    copy_expression_policy: Literal["avoid_direct_positioning_terms", "limited_direct_expression", "exact_user_copy"] = "avoid_direct_positioning_terms"
    preferred_channels: list[PositioningChannel] = Field(default_factory=lambda: ["visual_style", "composition", "lighting", "color", "typography", "negative_space"])
    copy_should_carry_positioning: bool = False
    direct_positioning_terms_allowed: list[str] = Field(default_factory=list)
    direct_positioning_terms_avoided: list[str] = Field(default_factory=list)
    rationale: list[str] = Field(default_factory=list)
    confidence: float = Field(default=0.8, ge=0.0, le=1.0)


class ProductExpressionBasis(BaseModel):
    product_identity: str
    verified_product_cues: list[EvidenceItem] = Field(default_factory=list)
    permissible_sensory_cues: list[EvidenceItem] = Field(default_factory=list)
    contextual_cues: list[EvidenceItem] = Field(default_factory=list)
    visual_cues: list[EvidenceItem] = Field(default_factory=list)
    unsupported_cues: list[str] = Field(default_factory=list)
    unknown_cues: list[str] = Field(default_factory=list)
    selected_headline_basis_ids: list[str] = Field(default_factory=list)
    selected_support_basis_ids: list[str] = Field(default_factory=list)


class NativeCopyCandidate(BaseModel):
    candidate_id: str
    strategy: Literal["product_name_first", "product_attribute_first", "sensory_first", "context_first", "minimal_identity"]
    headline: str
    supporting_copy: str | None = None
    closing_copy: str | None = None
    action_cta: str | None = None
    headline_basis_ids: list[str] = Field(default_factory=list)
    support_basis_ids: list[str] = Field(default_factory=list)
    language: Literal["korean", "english", "mixed"] = "korean"
    positioning_realization_mode: Literal["implicit", "balanced", "explicit"] = "implicit"
    direct_positioning_terms_used: list[str] = Field(default_factory=list)
    sensory_terms_used: list[str] = Field(default_factory=list)
    text_block_count: int = Field(default=1, ge=1, le=2)
    total_character_count: int = Field(default=0, ge=0, le=80)


class NativeCopyScorecard(BaseModel):
    candidate_id: str
    product_identity_clarity: float = Field(ge=0.0, le=1.0)
    product_centeredness: float = Field(ge=0.0, le=1.0)
    sensory_specificity: float = Field(ge=0.0, le=1.0)
    evidence_grounding: float = Field(ge=0.0, le=1.0)
    consumer_naturalness: float = Field(ge=0.0, le=1.0)
    positioning_alignment: float = Field(ge=0.0, le=1.0)
    headline_strength: float = Field(ge=0.0, le=1.0)
    support_complementarity: float = Field(ge=0.0, le=1.0)
    restraint: float = Field(ge=0.0, le=1.0)
    native_typography_fit: float = Field(ge=0.0, le=1.0)
    direct_positioning_penalty: float = Field(ge=0.0, le=1.0)
    generic_prestige_penalty: float = Field(ge=0.0, le=1.0)
    abstract_language_penalty: float = Field(ge=0.0, le=1.0)
    repetition_penalty: float = Field(ge=0.0, le=1.0)
    unsupported_claim_penalty: float = Field(ge=0.0, le=1.0)
    total_score: float = Field(ge=0.0, le=1.0)
    blocked: bool = False
    blocking_reasons: list[str] = Field(default_factory=list)


class NativeCopyStrategyBundle(BaseModel):
    product_expression_basis: ProductExpressionBasis
    positioning_plan: PositioningRealizationPlan
    candidates: list[NativeCopyCandidate] = Field(default_factory=list)
    scorecards: list[NativeCopyScorecard] = Field(default_factory=list)
    recommended_candidate_id: str | None = None
    requires_revision: bool = False
    revision_reasons: list[str] = Field(default_factory=list)


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
    consumer_facing_copy: bool = False
    meta_instruction_absent: bool = False
    user_request_transformed: bool = False
    product_identity_clean: bool = False
    copy_relevance_score: float = Field(default=0.0, ge=0.0, le=1.0)
    headline_quality_score: float = Field(default=0.0, ge=0.0, le=1.0)
    positioning_alignment_score: float = Field(default=0.0, ge=0.0, le=1.0)
    failure_reasons: list[str] = Field(default_factory=list)
    revision_instructions: list[str] = Field(default_factory=list)
    provider_metadata: dict = Field(default_factory=dict)
    selected_candidate_id: str | None = None
    positioning_realization_plan: dict = Field(default_factory=dict)
    candidate_scorecard: dict = Field(default_factory=dict)
    alternative_candidate_summaries: list[dict] = Field(default_factory=list)


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
    meta_instruction_exposed: bool = False
    consumer_facing_copy_score: float = Field(default=0.0, ge=0.0, le=1.0)
    copy_semantic_quality_score: float = Field(default=0.0, ge=0.0, le=1.0)
    literal_positioning_language_detected: bool = False
    product_centered_copy_score: float = Field(default=0.0, ge=0.0, le=1.0)
    sensory_grounding_score: float = Field(default=0.0, ge=0.0, le=1.0)
    positioning_realization_score: float = Field(default=0.0, ge=0.0, le=1.0)
    copy_restraint_score: float = Field(default=0.0, ge=0.0, le=1.0)
    headline_support_complementarity: float = Field(default=0.0, ge=0.0, le=1.0)
    decision: Literal["accept", "manual_review", "reject"]
    failure_reasons: list[str] = Field(default_factory=list)
