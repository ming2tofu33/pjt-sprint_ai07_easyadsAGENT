"""LLM/LangGraph marketing schemas for EasyAds v1."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

from orchestrator.app.schemas.llm_model_policy import UserPlan
from orchestrator.app.t2i.schemas import T2IRequest, T2IResult


EntryMode = Literal["chat_start", "photo_start", "reference_start"]

GenerationRoute = Literal[
    "text_to_image",
    "reference_guided_t2i",
    "product_composite",
    "product_inpainting",
    "interior_integration",
    "typography_only",
]

GenerationEngine = Literal["mock", "sd35_large", "flux", "gpt_image_2"]

RenderProfile = Literal["fast", "balanced", "premium_local", "premium_api", "benchmark"]

CopyGenerationMode = Literal["suggest_candidates", "auto_pilot", "no_copy", "custom_input"]

AdFormat = Literal[
    "instagram_feed",
    "instagram_story",
    "poster",
    "flyer",
    "product_detail",
    "banner",
]

Platform = Literal[
    "instagram",
    "offline",
    "web",
    "naver_smartstore",
    "naver_place",
    "danggeun",
    "etc",
]

AspectRatio = Literal["1:1", "4:5", "9:16", "16:9", "A4_vertical", "custom"]

JobStatus = Literal[
    "created",
    "input_received",
    "analyzing_image",
    "preprocessing_image",
    "preprocessing_reference_image",
    "preprocessing_product_image",
    "extracting_reference_style",
    "validating_context",
    "waiting_user_selection",
    "updating_state",
    "planning_format",
    "copywriting",
    "optimizing_prompt",
    "rendering_prompt",
    "t2i_queued",
    "t2i_running",
    "background_validating",
    "waiting_candidate_selection",
    "overlaying_text",
    "final_validating",
    "waiting_revision",
    "done",
    "failed",
    "binding_tone",
    "selecting_copy_mode",
    "generating_copy_candidates",
    "waiting_copy_selection",
    "applying_selected_copy",
    "waiting_custom_copy_input",
    "validating_custom_copy",
    "bypassing_copy",
]

CopySpace = Literal[
    "top",
    "top_left",
    "top_right",
    "center",
    "bottom",
    "bottom_left",
    "bottom_right",
    "left",
    "right",
    "none",
]

MissingField = Literal[
    "business_type",
    "item_or_service",
    "region_type",
    "target_persona",
    "promotion_goal",
    "brand_tone",
    "usp",
    "ad_format",
    "platform",
    "aspect_ratio",
    "time_context",
    "price_or_discount",
    "brand_name",
    "location_text",
    "contact_or_order_method",
    "custom_request",
    "copy_generation_mode",
    "user_custom_headline",
    "user_custom_subcopy",
]

ImageRole = Literal["product_photo", "food_photo", "interior_photo", "flat_background", "unknown"]
ImageFeatureCategory = Literal["food", "product", "interior", "flat", "person", "unknown"]
ReferenceSource = Literal["gallery", "user_upload", "system"]
OverlayStyle = Literal["none", "gradient", "solid_box", "glassmorphism", "stroke_shadow"]
OutputChannel = Literal["instagram_feed", "instagram_story", "naver_place", "smartstore_thumbnail", "flyer", "banner"]


class ConversationMessage(BaseModel):
    role: Literal["user", "assistant", "system", "tool"]
    content: str
    created_at: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class MarketingContext(BaseModel):
    business_type: str | None = None
    item_or_service: str | None = None
    region_type: str | None = None
    target_persona: str | None = None
    promotion_goal: str | None = None
    brand_tone: str | None = None
    usp: str | list[str] | None = None
    time_context: str | None = None
    price_or_discount: str | None = None
    brand_name: str | None = None
    location_text: str | None = None
    contact_or_order_method: str | None = None
    extra: dict[str, Any] = Field(default_factory=dict)


class ProgressState(BaseModel):
    current_step: int = Field(default=0, ge=0)
    total_steps: int = Field(default=0, ge=0)
    current_label: str = ""
    skipped_steps: list[str] = Field(default_factory=list)
    remaining_fields: list[MissingField] = Field(default_factory=list)
    can_skip_question_screen: bool = False
    status: JobStatus | None = None
    message: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class AdFormatSpec(BaseModel):
    ad_format: AdFormat
    platform: Platform
    aspect_ratio: AspectRatio
    width: int = Field(..., ge=1)
    height: int = Field(..., ge=1)
    information_density: Literal["low", "medium", "high"] = "medium"
    visual_priority: Literal[
        "product_hero",
        "mood_first",
        "information_first",
        "detail_explanation",
        "click_conversion",
    ] = "mood_first"
    output_strategy: Literal[
        "generate_text_free_background_then_overlay",
        "template_composite",
        "multi_section_layout",
        "product_preserving_edit",
        "typography_only",
    ]
    metadata: dict[str, Any] = Field(default_factory=dict)



class InitialMarketingRequest(BaseModel):
    entry_mode: EntryMode = "chat_start"
    user_input: str = Field(..., min_length=1)
    prompt_json: dict[str, Any] | None = None
    context: MarketingContext | None = None
    image_input: ImageInput | None = None
    reference_input: ReferenceInput | None = None
    source_image_path: str | None = None
    reference_image_path: str | None = None
    vision_preprocess_mode: str | None = None
    render_profile: RenderProfile = "balanced"
    requested_ad_format: str | None = None
    requested_platform: str | None = None
    project_id: str | None = None
    user_id: str | None = None
    organization_id: str | None = None
    job_id: str | None = None
    thread_id: str | None = None
    copy_generation_mode: CopyGenerationMode | None = None
    user_custom_headline: str | None = None
    user_custom_subcopy: str | None = None
    user_plan: UserPlan = "free"

class ValidatorOutput(BaseModel):
    context: MarketingContext
    missing_fields: list[MissingField]
    confidence: float = Field(..., ge=0.0, le=1.0)
    needs_user_selection: bool
    inferred_entry_mode: EntryMode | None = None
    inferred_generation_route: GenerationRoute | None = None
    inferred_ad_format: AdFormatSpec | None = None
    progress_state: ProgressState | None = None
    reasoning_summary: str | None = None


class OptionItem(BaseModel):
    id: int
    label: str
    value: str
    description: str | None = None
    icon: str | None = None
    recommended: bool = False


class OptionQuestion(BaseModel):
    field: MissingField
    question: str
    options: list[OptionItem]
    required: bool = True
    multi_select: bool = False
    allow_custom: bool = True
    progress_state: ProgressState | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class UserSelectionRequest(BaseModel):
    job_id: str
    thread_id: str
    field: MissingField
    value: str | list[str]
    custom_text: str | None = None


class Zone(BaseModel):
    x: float = Field(..., ge=0.0, le=1.0)
    y: float = Field(..., ge=0.0, le=1.0)
    width: float = Field(..., gt=0.0, le=1.0)
    height: float = Field(..., gt=0.0, le=1.0)


class TextZone(Zone):
    role: Literal["headline", "subcopy", "cta", "price", "disclaimer", "free"] = "free"
    max_chars: int | None = Field(default=None, ge=1)
    align: Literal["left", "center", "right"] = "center"


class LayoutSpec(BaseModel):
    layout_type: Literal[
        "single_panel",
        "story",
        "poster",
        "flyer",
        "banner",
        "product_detail",
        "single_hero",
        "story_vertical",
        "top_headline_bottom_product",
        "flyer_information",
        "split_text_image",
        "multi_section",
    ] = "single_panel"
    copy_space: CopySpace = "bottom"
    safe_area: Zone | None = None
    text_zones: list[TextZone] = Field(default_factory=list)
    product_zone: Zone | None = None
    cta_zone: Zone | None = None
    background_zone: Zone | None = None
    overlay_style: OverlayStyle = "gradient"
    text_align: Literal["left", "center", "right"] = "center"
    max_text_density: Literal["low", "medium", "high"] = "medium"
    metadata: dict[str, Any] = Field(default_factory=dict)


class MarketingCopy(BaseModel):
    headline: str
    subcopy: str | None = None
    cta: str | None = None
    price_line: str | None = None
    period_line: str | None = None
    hashtags: list[str] = Field(default_factory=list)
    disclaimer: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class CopyCandidate(BaseModel):
    id: str
    headline: str
    subcopy: str | None = None
    cta: str | None = None
    hashtags: list[str] = Field(default_factory=list)
    tone_label: str | None = None
    rationale: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class CopyCandidateListOutput(BaseModel):
    candidates: list[CopyCandidate]
    recommended_candidate_id: str | None = None
    generation_mode: Literal["suggest_candidates"] = "suggest_candidates"
    metadata: dict[str, Any] = Field(default_factory=dict)


class CustomCopyInput(BaseModel):
    headline: str
    subcopy: str | None = None
    cta: str | None = None
    hashtags: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class ToneBindingOutput(BaseModel):
    tone_profile: str
    copy_constraints: list[str] = Field(default_factory=list)
    recommended_copy_mode: CopyGenerationMode | None = None
    forbidden_claims: list[str] = Field(default_factory=list)
    channel_copy_rules: list[str] = Field(default_factory=list)
    typography_hint: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class CopyModeInferenceOutput(BaseModel):
    copy_generation_mode: CopyGenerationMode
    confidence: float = Field(..., ge=0.0, le=1.0)
    source: Literal["explicit_user_choice", "heuristic", "default"]
    reasoning_summary: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class CopywritingOutput(BaseModel):
    marketing_copy: MarketingCopy
    tone_profile: dict[str, Any] = Field(default_factory=dict)
    alternatives: list[MarketingCopy] = Field(default_factory=list)
    progress_state: ProgressState | None = None
    rationale: str | None = None


class ImagePrompt(BaseModel):
    subject: str
    style: str
    lighting: str
    composition: str
    copy_space: CopySpace
    negative_prompt: str
    scene: str | None = None
    color_palette: list[str] = Field(default_factory=list)
    avoid_text: bool = True
    metadata: dict[str, Any] = Field(default_factory=dict)


class UserReadableImageGuide(BaseModel):
    summary: str
    subject_ko: str | None = None
    mood_ko: str | None = None
    composition_ko: str | None = None
    copy_space_ko: str | None = None
    style_keywords: list[str] = Field(default_factory=list)
    copy_space: CopySpace | None = None
    warnings: list[str] = Field(default_factory=list)


class PromptOptimizationOutput(BaseModel):
    image_prompt: ImagePrompt
    user_readable_image_guide: UserReadableImageGuide | None = None
    negative_prompt: str | None = None
    progress_state: ProgressState | None = None
    rationale: str | None = None


class PromptRenderOutput(BaseModel):
    engine: GenerationEngine
    positive_prompt: str
    negative_prompt: str | None = None
    render_profile: RenderProfile = "balanced"
    render_notes: list[str] = Field(default_factory=list)
    width: int = Field(..., ge=1)
    height: int = Field(..., ge=1)
    metadata: dict[str, Any] = Field(default_factory=dict)


class RefactoringOutput(BaseModel):
    marketing_copy: MarketingCopy
    ad_format_spec: AdFormatSpec
    layout_spec: LayoutSpec
    image_prompt: ImagePrompt
    context: MarketingContext
    user_readable_image_guide: UserReadableImageGuide | None = None
    rationale: str | None = None


class ImageInput(BaseModel):
    image_id: str
    original_path: str
    preprocessed_path: str | None = None
    filename: str | None = None
    mime_type: str | None = None
    width: int | None = None
    height: int | None = None
    file_size_bytes: int | None = None
    image_role: ImageRole = "unknown"
    metadata: dict[str, Any] = Field(default_factory=dict)


class ImageFeatures(BaseModel):
    category: ImageFeatureCategory
    subject_summary: str | None = None
    detected_objects: list[str] = Field(default_factory=list)
    color_palette: list[str] = Field(default_factory=list)
    mood: list[str] = Field(default_factory=list)
    lighting: str | None = None
    composition: str | None = None
    background_style: str | None = None
    copy_space_available: bool | None = None
    recommended_copy_space: CopySpace | None = None
    product_mask_path: str | None = None
    product_cutout_path: str | None = None
    depth_map_path: str | None = None
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    raw_vlm_output: dict[str, Any] = Field(default_factory=dict)


class ReferenceInput(BaseModel):
    reference_id: str
    reference_path: str
    category: str | None = None
    source: ReferenceSource = "gallery"
    metadata: dict[str, Any] = Field(default_factory=dict)


class ReferenceStyleSpec(BaseModel):
    color_palette: list[str] = Field(default_factory=list)
    mood: list[str] = Field(default_factory=list)
    layout: str | None = None
    lighting: str | None = None
    typography_hint: str | None = None
    background_style: str | None = None
    ad_style_prompt: str | None = None


class GeneratedImageCandidate(BaseModel):
    image_id: str
    image_path: str
    width: int
    height: int
    engine: GenerationEngine
    seed: int | None = None
    latency_ms: int | None = None
    background_validation: BackgroundValidationReport | None = None
    final_validation: FinalValidationReport | None = None
    quality_score: float | None = None
    selected: bool = False
    metadata: dict[str, Any] = Field(default_factory=dict)


class TextOverlayConfig(BaseModel):
    marketing_copy: MarketingCopy
    ad_format_spec: AdFormatSpec
    layout_spec: LayoutSpec
    copy_space: CopySpace
    font_path: str | None = None
    brand_color: str = "#E85D75"
    text_color: str = "#FFFFFF"
    overlay_style: OverlayStyle = "gradient"
    output_channel: OutputChannel = "instagram_feed"


# Legacy marketing-level validation schemas remain here for compatibility with
# earlier state/report imports. TLFP render/readability reports live in
# orchestrator.app.schemas.text_layout.
class BackgroundValidationReport(BaseModel):
    overall_pass: bool
    text_artifact_pass: bool
    watermark_pass: bool
    copy_space_pass: bool
    visual_quality_pass: bool
    brand_safety_pass: bool
    detected_text_artifacts: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    issues: list[str] = Field(default_factory=list)
    retry_recommended: bool = False
    retry_reason: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class FinalValidationReport(BaseModel):
    overall_pass: bool
    ocr_pass: bool
    rule_pass: bool
    readability_pass: bool
    layout_pass: bool
    visual_pass: bool
    expected_text: list[str] = Field(default_factory=list)
    detected_text: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    issues: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class ValidationReport(BaseModel):
    overall_pass: bool
    background: BackgroundValidationReport | None = None
    final: FinalValidationReport | None = None
    product_preservation_pass: bool | None = None
    product_similarity_score: float | None = None
    warnings: list[str] = Field(default_factory=list)
    issues: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class JobStatusResponse(BaseModel):
    job_id: str
    thread_id: str
    status: JobStatus
    entry_mode: EntryMode
    progress_state: ProgressState | None = None
    context: MarketingContext | None = None
    ad_format_spec: AdFormatSpec | None = None
    layout_spec: LayoutSpec | None = None
    image_features: ImageFeatures | None = None
    reference_style: ReferenceStyleSpec | None = None
    option_question: OptionQuestion | None = None
    marketing_copy: MarketingCopy | None = None
    user_readable_image_guide: UserReadableImageGuide | None = None
    prompt_render_output: PromptRenderOutput | None = None
    t2i_result: T2IResult | None = None
    candidates: list[GeneratedImageCandidate] = Field(default_factory=list)
    selected_candidate_id: str | None = None
    final_image_path: str | None = None
    validation_report: ValidationReport | None = None
    error_message: str | None = None


class ArtifactRef(BaseModel):
    artifact_id: str
    artifact_type: str
    path: str
    label: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class ErrorInfo(BaseModel):
    code: str
    message: str
    recoverable: bool = True
    details: dict[str, Any] = Field(default_factory=dict)
