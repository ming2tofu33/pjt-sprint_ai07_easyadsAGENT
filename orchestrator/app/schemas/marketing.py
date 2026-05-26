from typing import Any, Literal

from pydantic import BaseModel, Field


BusinessType = Literal["restaurant", "cafe", "beauty_salon", "bar", "fitness", "academy", "store", "custom"]
RegionType = Literal["office_district", "university_area", "trendy_district", "tourist_spot", "residential_area", "custom"]
TargetPersona = Literal["college_student", "office_worker", "young_social", "tourist", "family_local", "custom"]
PromotionGoal = Literal["launch", "discount_event", "reservation_cta", "brand_awareness", "retention", "custom"]
BrandTone = Literal["warm_cozy", "hip_trendy", "premium_refined", "bold_urgent", "natural_healthy", "custom"]
USP = Literal["group_reservation", "view_spot", "value_for_money", "late_hours", "fresh_ingredients", "custom"]
CopySpace = Literal["top", "bottom", "left", "right", "center", "top-right"]
GenerationEngine = Literal["sd35_large", "flux", "gpt_image_2"]
JobStatus = Literal[
    "created",
    "validating",
    "waiting_user_selection",
    "refactoring",
    "t2i_queued",
    "t2i_running",
    "overlaying_text",
    "validating_result",
    "done",
    "failed",
]


class MarketingContext(BaseModel):
    """Structured marketing context shared by validator and refactoring nodes."""

    business_type: BusinessType | None = None
    item_or_service: str | None = None
    region_type: RegionType | None = None
    target_persona: TargetPersona | None = None
    promotion_goal: PromotionGoal | None = None
    brand_tone: BrandTone | None = None
    usp: USP | None = None
    extra: dict[str, Any] = Field(default_factory=dict)


class InitialMarketingRequest(BaseModel):
    """Initial user request for the T2I-first MVP flow."""

    user_input: str = Field(..., min_length=1)
    prompt_json: dict[str, Any] | None = None
    context: MarketingContext | None = None
    preferred_engine: GenerationEngine = "sd35_large"


class ValidatorOutput(BaseModel):
    """Validator node output with missing context fields fixed to known keys."""

    context: MarketingContext
    missing_fields: list[Literal["business_type", "item_or_service", "region_type", "target_persona", "promotion_goal", "brand_tone", "usp"]]
    confidence: float = Field(..., ge=0.0, le=1.0)
    needs_user_selection: bool


class OptionItem(BaseModel):
    """One selectable option shown to the user."""

    label: str = Field(..., min_length=1)
    value: str = Field(..., min_length=1)
    description: str | None = None


class OptionQuestion(BaseModel):
    """Options node output for a single missing field."""

    field: Literal["business_type", "item_or_service", "region_type", "target_persona", "promotion_goal", "brand_tone", "usp"]
    question: str = Field(..., min_length=1)
    options: list[OptionItem] = Field(..., min_length=1)
    required: bool = True
    multi_select: bool = False


class UserSelectionRequest(BaseModel):
    """Resume payload after a user selects an option."""

    job_id: str = Field(..., min_length=1)
    field: Literal["business_type", "item_or_service", "region_type", "target_persona", "promotion_goal", "brand_tone", "usp"]
    value: str | list[str] = Field(..., min_length=1)


class MarketingCopy(BaseModel):
    """Final ad copy that will be rendered by text overlay, not T2I."""

    headline: str = Field(..., min_length=1)
    subcopy: str = Field(..., min_length=1)
    cta: str = Field(..., min_length=1)
    disclaimer: str | None = None


class ImagePrompt(BaseModel):
    """Six-field prompt schema for text-free poster background generation."""

    subject: str = Field(..., min_length=1)
    style: str = Field(..., min_length=1)
    lighting: str = Field(..., min_length=1)
    composition: str = Field(..., min_length=1)
    copy_space: CopySpace
    negative_prompt: str = Field(..., min_length=1)


class RefactoringOutput(BaseModel):
    """Refactoring node output: copy plus image prompt."""

    marketing_copy: MarketingCopy
    image_prompt: ImagePrompt
    context: MarketingContext
    rationale: str | None = None


class T2IRequest(BaseModel):
    """Common request contract for SD3.5 Large, FLUX, and GPT-image-2 engines."""

    job_id: str = Field(..., min_length=1)
    engine: GenerationEngine
    image_prompt: ImagePrompt
    width: int = Field(default=1024, ge=512, le=2048)
    height: int = Field(default=1024, ge=512, le=2048)
    seed: int | None = None
    num_inference_steps: int | None = Field(default=None, ge=1, le=80)
    guidance_scale: float | None = Field(default=None, ge=0.0, le=20.0)


class T2IResult(BaseModel):
    """Raw text-to-image generation result before text overlay."""

    job_id: str = Field(..., min_length=1)
    engine: GenerationEngine
    image_path: str = Field(..., min_length=1)
    width: int = Field(..., ge=1)
    height: int = Field(..., ge=1)
    seed: int | None = None
    latency_ms: int = Field(..., ge=0)
    metadata: dict[str, Any] = Field(default_factory=dict)


class TextOverlayConfig(BaseModel):
    """Text overlay parameters for rendering accurate Korean ad copy."""

    marketing_copy: MarketingCopy
    copy_space: CopySpace
    font_path: str | None = None
    brand_color: str = "#E85D75"
    text_color: str = "#FFFFFF"
    output_channel: Literal["instagram_feed", "instagram_story", "naver_place", "smartstore_thumbnail"] = "instagram_feed"


class ValidationReport(BaseModel):
    """Validation summary for final downloadable poster output."""

    overall_pass: bool
    ocr_pass: bool
    rule_pass: bool
    visual_pass: bool
    expected_text: list[str] = Field(default_factory=list)
    detected_text: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    issues: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class JobStatusResponse(BaseModel):
    """Status response returned to the UI or API client."""

    job_id: str = Field(..., min_length=1)
    status: JobStatus
    context: MarketingContext | None = None
    option_question: OptionQuestion | None = None
    refactoring_output: RefactoringOutput | None = None
    t2i_result: T2IResult | None = None
    final_image_path: str | None = None
    validation_report: ValidationReport | None = None
    error_message: str | None = None

