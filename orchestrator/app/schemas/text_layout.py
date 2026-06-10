"""Text-Layout-First Pipeline schemas."""

from __future__ import annotations

from typing import Any, Literal
from uuid import uuid4

from pydantic import BaseModel, Field, model_validator


CopyRole = Literal["headline", "subheadline", "promotion", "price", "cta", "store_info", "disclaimer", "badge", "body"]
StyleProfile = Literal["cute", "premium", "clean", "trendy", "emotional", "event"]
OverlayTreatment = Literal["plain", "drop_shadow", "stroke", "gradient_panel", "solid_panel", "blur_backdrop", "sticker_badge"]
TypographyOverlayTreatment = Literal[
    "none",
    "soft_shadow",
    "soft_gradient_veil",
    "localized_blur",
    "content_fit_plate",
    "small_chip",
    "editorial_underline",
]
TypographyRole = Literal["eyebrow", "brand_label", "headline", "subheadline", "body", "price", "cta", "disclaimer"]
AnchorPosition = Literal[
    "top_left",
    "top_center",
    "top_right",
    "middle_left",
    "middle_center",
    "middle_right",
    "bottom_left",
    "bottom_center",
    "bottom_right",
]
TextAlignment = Literal["left", "center", "right", "auto"]
LayoutTemplate = Literal[
    "top_headline_center_product_bottom_cta",
    "left_text_right_product",
    "right_text_left_product",
    "dynamic_side_split",
    "bottom_overlay_panel",
    "multi_zone_flyer",
    "minimal_corner",
    "centered_hero",
    "no_text",
]
IntentHierarchy = Literal["editorial_product", "conversion", "menu_showcase", "minimal_premium", "cute_promo", "information_first"]
CtaVisibility = Literal["required", "optional", "hidden"]
CtaStyle = Literal["none", "text_link", "small_label", "pill_button", "solid_button"]
ExclusionZoneType = Literal["product", "face", "hand", "person", "ocr_artifact", "high_saliency"]
DominantSubjectSide = Literal["left", "right", "center", "distributed", "unknown"]
LayoutRefinementAction = Literal["render", "reduce_information", "rewrite_copy", "regenerate_background", "manual_review"]
WcagGrade = Literal["AAA", "AA", "AA_LARGE", "FAIL"]
SuggestedAction = Literal["none", "swap_color", "add_overlay", "regenerate", "shrink"]
RuleCheck = Literal["not_run", "pass", "fail"]
ResultStatus = Literal["done", "failed"]


class NormalizedBBox(BaseModel):
    x: float = Field(..., ge=0.0, le=1.0)
    y: float = Field(..., ge=0.0, le=1.0)
    w: float = Field(..., gt=0.0, le=1.0)
    h: float = Field(..., gt=0.0, le=1.0)

    @model_validator(mode="after")
    def validate_bounds(self):
        if self.x + self.w > 1.0:
            raise ValueError("x + w must be <= 1.0")
        if self.y + self.h > 1.0:
            raise ValueError("y + h must be <= 1.0")
        return self

    def to_pixels(self, canvas_w: int, canvas_h: int) -> tuple[int, int, int, int]:
        return (
            round(self.x * canvas_w),
            round(self.y * canvas_h),
            round(self.w * canvas_w),
            round(self.h * canvas_h),
        )

    def area_ratio(self) -> float:
        return self.w * self.h


class CopyItem(BaseModel):
    role: CopyRole
    text: str
    priority: int = 5
    locale: str = "ko-KR"
    forced_weight: int | None = None
    forced_color: str | None = None
    is_renderable: bool = True
    skip_reason: str | None = None


class CopySpec(BaseModel):
    schema_version: Literal["1.0"] = "1.0"
    spec_id: str = Field(default_factory=lambda: f"copy_spec_{uuid4().hex}")
    items: list[CopyItem] = Field(default_factory=list)
    copy_mode: str = "standard"
    tone_profile: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_headline(self):
        if self.copy_mode != "no_copy" and not any(item.role == "headline" for item in self.items):
            raise ValueError("CopySpec requires a headline unless copy_mode is no_copy")
        return self

    def get_renderable(self) -> list[CopyItem]:
        return [item for item in self.items if item.is_renderable]


class FontMetric(BaseModel):
    font_family: str = "Pretendard"
    font_path: str | None = None
    base_size_ratio: float = Field(..., gt=0.0, le=1.0)
    min_size_ratio: float = Field(..., gt=0.0, le=1.0)
    max_size_ratio: float = Field(..., gt=0.0, le=1.0)
    weight: int = Field(..., ge=100, le=1000)
    letter_spacing_em: float = 0.0
    line_height_em: float = Field(default=1.15, gt=0.0)


class TextSlot(BaseModel):
    slot_id: str
    role: CopyRole
    bbox: NormalizedBBox
    bound_copy_id: str | None = None
    rendered_text: str | None = None
    rendered_lines: list[str] = Field(default_factory=list)
    effective_font_size_px: int | None = None
    effective_weight: int | None = None
    font_metric: FontMetric
    alignment: TextAlignment = "auto"
    anchor: AnchorPosition = "middle_center"
    text_color: str = "#FFFFFF"
    overlay_treatment: OverlayTreatment = "drop_shadow"
    overlay_color: str | None = None
    overlay_opacity: float = Field(default=0.0, ge=0.0, le=1.0)
    inner_padding_ratio: float = Field(default=0.04, ge=0.0, le=0.5)
    max_lines: int = Field(default=2, ge=1)
    reserve_in_image: bool = True


class TextLayoutSpec(BaseModel):
    schema_version: Literal["1.0"] = "1.0"
    spec_id: str = Field(default_factory=lambda: f"text_layout_{uuid4().hex}")
    template: LayoutTemplate
    canvas_width: int = Field(..., ge=1)
    canvas_height: int = Field(..., ge=1)
    auto_find_empty_space: bool = Field(default=False)
    safe_margin_ratio: float = Field(default=0.06, ge=0.0, le=0.5)
    slots: list[TextSlot] = Field(default_factory=list)
    reserved_text_areas: list[NormalizedBBox] = Field(default_factory=list)
    product_zone: NormalizedBBox | None = None

    @model_validator(mode="after")
    def sync_reserved_text_areas(self):
        if self.template != "no_text" and not self.reserved_text_areas:
            self.reserved_text_areas = [slot.bbox for slot in self.slots if slot.reserve_in_image]
        return self

    def get_slot_by_role(self, role: CopyRole) -> TextSlot | None:
        return next((slot for slot in self.slots if slot.role == role), None)


class ExclusionZone(BaseModel):
    zone_id: str
    zone_type: ExclusionZoneType
    bbox: NormalizedBBox
    confidence: float = Field(..., ge=0.0, le=1.0)
    hard_exclusion: bool = False
    source: str


class ImageLayoutAnalysis(BaseModel):
    canvas_width: int = Field(..., ge=1)
    canvas_height: int = Field(..., ge=1)
    exclusion_zones: list[ExclusionZone] = Field(default_factory=list)
    suggested_negative_space_regions: list[NormalizedBBox] = Field(default_factory=list)
    dominant_subject_side: DominantSubjectSide = "unknown"
    edge_density_summary: dict[str, float] = Field(default_factory=dict)
    local_variance_summary: dict[str, float] = Field(default_factory=dict)
    saliency_summary: dict[str, float] = Field(default_factory=dict)
    luminance_summary: dict[str, float] = Field(default_factory=dict)
    analysis_confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    metadata: dict[str, Any] = Field(default_factory=dict)


class LayoutCandidateScore(BaseModel):
    candidate_id: str
    template: str
    final_score: float
    product_overlap_ratio: float = Field(..., ge=0.0)
    face_hand_overlap_ratio: float = Field(..., ge=0.0)
    saliency_penalty: float = Field(..., ge=0.0)
    edge_density_penalty: float = Field(..., ge=0.0)
    contrast_penalty: float = Field(..., ge=0.0)
    safe_margin_penalty: float = Field(..., ge=0.0)
    text_area_continuity_score: float = Field(..., ge=0.0, le=1.0)
    composition_balance_score: float = Field(..., ge=0.0, le=1.0)
    reference_alignment_score: float = Field(..., ge=0.0, le=1.0)
    copy_fit_score: float = Field(..., ge=0.0, le=1.0)
    hard_rejected: bool = False
    rejection_reasons: list[str] = Field(default_factory=list)


class LayoutRefinementResult(BaseModel):
    selected_candidate_id: str | None = None
    selected_layout: TextLayoutSpec | None = None
    candidates: list[LayoutCandidateScore] = Field(default_factory=list)
    action: LayoutRefinementAction
    retry_feedback: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class LayoutCopyFitReport(BaseModel):
    overall_fit: bool
    role_results: list[dict[str, Any]] = Field(default_factory=list)
    removed_optional_roles: list[str] = Field(default_factory=list)
    selected_copy_id: str | None = None
    rewrite_required: bool = False
    overflow_ratio: float = Field(default=0.0, ge=0.0)
    warnings: list[str] = Field(default_factory=list)


class TypographyRule(BaseModel):
    headline_font: str
    body_font: str
    headline_weight: int = Field(..., ge=100, le=1000)
    body_weight: int = Field(..., ge=100, le=1000)
    headline_size_ratio: float = Field(..., gt=0.0, le=1.0)
    body_size_ratio: float = Field(..., gt=0.0, le=1.0)
    letter_spacing_em: float = 0.0
    line_height_em: float = Field(default=1.15, gt=0.0)
    primary_color: str
    accent_color: str
    text_color_on_light: str
    text_color_on_dark: str
    default_overlay: OverlayTreatment
    use_text_plate: bool = False
    plate_style: str | None = None


class TypographyRoleStyle(BaseModel):
    role: TypographyRole
    family_id: str
    font_id: str | None = None
    weight: int = Field(..., ge=100, le=1000)
    size_ratio: float = Field(..., gt=0.0, le=1.0)
    min_size_ratio: float = Field(..., gt=0.0, le=1.0)
    max_size_ratio: float = Field(..., gt=0.0, le=1.0)
    letter_spacing_em: float = 0.0
    line_height_em: float = Field(default=1.15, gt=0.0)
    text_color: str | None = None
    alignment: Literal["left", "center", "right"] = "left"
    max_lines: int = Field(default=2, ge=1)
    overlay_treatment: TypographyOverlayTreatment = "none"


class TypographyRenderTrace(BaseModel):
    role: str
    font_id: str
    family_id: str
    resolved_weight: int
    source: str
    effective_font_size_px: int
    rendered_lines: list[str]
    rendered_bbox_px: tuple[int, int, int, int]
    letter_spacing_px: float
    line_height_px: float
    text_color: str
    contrast_ratio_min: float
    contrast_ratio_average: float
    overlay_treatment: str
    overlay_bbox_px: tuple[int, int, int, int] | None = None
    fallback_used: bool = False
    warnings: list[str] = Field(default_factory=list)


class TextStyleSpec(BaseModel):
    schema_version: Literal["1.0"] = "1.0"
    profile: StyleProfile
    typography: TypographyRule
    brand_color_override: str | None = None
    brand_font_override: str | None = None
    role_styles: dict[str, Any] = Field(default_factory=dict)
    headline_style: TypographyRoleStyle | None = None
    body_style: TypographyRoleStyle | None = None
    cta_style: TypographyRoleStyle | None = None
    label_style: TypographyRoleStyle | None = None
    price_style: TypographyRoleStyle | None = None
    disclaimer_style: TypographyRoleStyle | None = None
    font_pair_id: str | None = None
    typography_art_direction: dict[str, Any] | None = None


class CopyVisualIntent(BaseModel):
    hierarchy: IntentHierarchy
    headline_emphasis: Literal["large_elegant", "large_bold", "medium_balanced", "minimal"]
    body_density: Literal["none", "low", "medium", "high"]
    cta_visibility: CtaVisibility
    cta_style: CtaStyle
    preferred_alignment: Literal["left", "center", "right", "adaptive"]
    typography_mood: Literal["premium_serif", "clean_sans", "rounded_friendly", "bold_promo", "editorial_mixed"]
    plate_policy: Literal["none", "subtle", "cta_only", "content_fit", "strong_panel"]
    product_text_relationship: Literal["side_by_side", "text_over_negative_space", "top_bottom", "centered_minimal"]
    reference_layout_hint: str | None = None
    reference_typography_hint: str | None = None
    reasoning_summary: str | None = None


class ImagePromptSpec(BaseModel):
    schema_version: Literal["1.0"] = "1.0"
    scene_description: str
    product_subject: str
    color_palette: list[str] = Field(default_factory=list)
    composition: str
    lighting: str
    reserved_text_areas: list[NormalizedBBox] = Field(default_factory=list)
    must_not_include_text: bool = True
    positive_prompt_en: str | None = None
    negative_prompt_en: str | None = None
    target_width: int = Field(..., ge=1)
    target_height: int = Field(..., ge=1)
    aspect_ratio: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class SlotReadability(BaseModel):
    slot_id: str
    role: CopyRole
    background_luminance: float = Field(..., ge=0.0, le=1.0)
    text_luminance: float = Field(..., ge=0.0, le=1.0)
    contrast_ratio: float = Field(..., ge=0.0)
    wcag_grade: WcagGrade
    out_of_safe_area: bool = False
    overlaps_product: bool = False
    clipped: bool = False
    suggested_text_color: str | None = None
    suggested_overlay: OverlayTreatment | None = None
    suggested_action: SuggestedAction = "none"


class ReadabilityReport(BaseModel):
    schema_version: Literal["1.0"] = "1.0"
    overall_pass: bool
    slots: list[SlotReadability] = Field(default_factory=list)
    avg_contrast_ratio: float = Field(..., ge=0.0)
    min_contrast_ratio: float = Field(..., ge=0.0)
    failed_slot_count: int = Field(..., ge=0)
    requires_regeneration: bool = False
    auto_fixes_applied: list[str] = Field(default_factory=list)
    remaining_issues: list[str] = Field(default_factory=list)


class BackgroundValidationReport(BaseModel):
    schema_version: Literal["1.0"] = "1.0"
    overall_pass: bool
    image_exists: bool
    image_path: str | None = None
    width: int | None = None
    height: int | None = None
    expected_width: int | None = None
    expected_height: int | None = None
    render_text_in_image: bool
    reserved_text_area_count: int = Field(..., ge=0)
    text_artifact_check: RuleCheck = "not_run"
    watermark_check: RuleCheck = "not_run"
    warnings: list[str] = Field(default_factory=list)
    issues: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class SafeAreaReport(BaseModel):
    schema_version: Literal["1.0"] = "1.0"
    overall_pass: bool
    reserved_text_area_count: int = Field(..., ge=0)
    product_overlap_warnings: list[str] = Field(default_factory=list)
    bbox_issues: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class RenderResult(BaseModel):
    schema_version: Literal["1.0"] = "1.0"
    background_image_path: str
    final_image_path: str
    rendered_slot_count: int = Field(..., ge=0)
    skipped_slot_count: int = Field(..., ge=0)
    warnings: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class FinalValidationReport(BaseModel):
    schema_version: Literal["1.0"] = "1.0"
    overall_pass: bool
    background_pass: bool
    safe_area_pass: bool
    readability_pass: bool | None = None
    no_copy: bool
    warnings: list[str] = Field(default_factory=list)
    issues: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class ResultPayload(BaseModel):
    schema_version: Literal["1.0"] = "1.0"
    job_id: str
    thread_id: str
    status: ResultStatus
    output_path: str | None = None
    background_image_path: str | None = None
    final_image_path: str | None = None
    copy_generation_mode: str | None = None
    has_text_overlay: bool
    validation_summary: dict[str, Any] = Field(default_factory=dict)
    artifact_refs: list[dict[str, Any]] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
