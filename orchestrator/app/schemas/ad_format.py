"""Ad format, copy presence, and panel planning contracts."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, model_validator


Placement = Literal[
    "instagram_feed_static",
    "instagram_story",
    "instagram_reel_cover",
    "facebook_feed",
    "google_display",
    "landing_page_hero",
    "product_detail_hero",
    "print_poster",
    "offline_flyer",
    "menu_board",
    "store_signage",
    "generic_social_square",
]
AspectRatio = Literal["1:1", "4:5", "9:16", "16:9", "3:4", "custom"]
InteractionMode = Literal["non_interactive_image", "platform_interactive", "html_or_landing_page", "print_or_offline", "qr_enabled"]
EmbeddedCtaPolicy = Literal["forbidden", "optional", "required", "platform_only"]
CreativeLane = Literal["visual_first", "information_design"]
TextDensityRange = Literal["none", "minimal", "low", "medium", "high"]
CreativeArchetype = Literal[
    "visual_editorial",
    "visual_minimal",
    "product_benefit_story",
    "product_information_poster",
    "promotion_sale_poster",
    "event_poster",
    "menu_or_price_board",
]
ReasonCode = Literal[
    "image_has_high_explanatory_power",
    "brand_awareness_goal",
    "editorial_visual_priority",
    "product_closeup",
    "multiple_verified_benefits",
    "promotion_present",
    "price_present",
    "period_present",
    "discount_present",
    "product_explanation_required",
    "event_information_required",
    "menu_information_required",
    "low_brand_awareness",
    "lower_funnel_conversion",
]
CopyPresenceMode = Literal[
    "image_only",
    "brand_only",
    "headline_only",
    "headline_plus_caption",
    "headline_plus_support",
    "offer_or_proof",
    "product_benefit_summary",
    "full_information_poster",
]
PanelType = Literal[
    "none",
    "left_information_column",
    "right_information_column",
    "top_headline_band",
    "bottom_benefit_strip",
    "floating_promotion_card",
    "circular_proof_badge",
    "split_screen_diagonal_panel",
    "organic_curved_panel",
    "full_poster_grid",
]
PanelGeometry = Literal["none", "rectangle", "rounded_rectangle", "circle", "pill", "diagonal", "organic_curve", "grid"]
PanelTreatment = Literal["none", "solid", "soft_solid", "soft_gradient", "translucent", "blurred", "paper_texture"]
ProductZone = Literal["left", "right", "center", "top", "bottom", "background_full"]
HierarchyZone = Literal[
    "brand_zone",
    "headline_zone",
    "subheadline_zone",
    "benefit_list_zone",
    "proof_badge_zone",
    "promotion_badge_zone",
    "price_zone",
    "period_zone",
    "footer_benefit_strip",
    "qr_or_contact_zone",
]


class PlatformSafeZoneSpec(BaseModel):
    top_ratio: float = Field(default=0.0, ge=0.0, le=0.5)
    bottom_ratio: float = Field(default=0.0, ge=0.0, le=0.5)
    left_ratio: float = Field(default=0.0, ge=0.0, le=0.5)
    right_ratio: float = Field(default=0.0, ge=0.0, le=0.5)
    reserved_for_platform_ui: list[str] = Field(default_factory=list)


class AdFormatContract(BaseModel):
    placement: Placement
    aspect_ratio: AspectRatio
    interaction_mode: InteractionMode
    platform_cta_available: bool
    embedded_cta_policy: EmbeddedCtaPolicy
    platform_safe_zones: PlatformSafeZoneSpec
    creative_lane: CreativeLane
    text_density_range: TextDensityRange
    caption_channel_available: bool = False
    required_information_fields: list[str] = Field(default_factory=list)
    rationale: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_cta_policy(self):
        if self.interaction_mode == "html_or_landing_page" and self.embedded_cta_policy not in {"forbidden", "platform_only"}:
            raise ValueError("landing/html placements must not embed image CTA buttons")
        if self.embedded_cta_policy == "platform_only" and not self.platform_cta_available:
            raise ValueError("platform_only CTA requires platform_cta_available")
        if self.interaction_mode == "qr_enabled" and "qr_destination" not in self.required_information_fields:
            raise ValueError("qr_enabled placements require qr_destination")
        return self


class CreativeLaneDecision(BaseModel):
    lane: CreativeLane
    archetype: CreativeArchetype
    reason_codes: list[ReasonCode]
    confidence: float = Field(ge=0.0, le=1.0)


class CopyPresencePlan(BaseModel):
    mode: CopyPresenceMode
    allowed_roles: list[str]
    forbidden_roles: list[str]
    max_text_area_ratio: float = Field(ge=0.0, le=0.75)
    min_text_area_ratio: float = Field(default=0.0, ge=0.0, le=0.75)
    visual_intrusion_budget: float = Field(ge=0.0, le=1.0)
    no_text_allowed: bool
    max_message_blocks: int = Field(ge=0, le=12)
    rationale: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_budget(self):
        if self.min_text_area_ratio > self.max_text_area_ratio:
            raise ValueError("min_text_area_ratio must be <= max_text_area_ratio")
        return self


class InformationPanelPlan(BaseModel):
    enabled: bool
    panel_type: PanelType
    geometry: PanelGeometry
    coverage_ratio: float = Field(ge=0.0, le=0.70)
    background_treatment: PanelTreatment
    product_zone: ProductZone
    hierarchy_zones: list[HierarchyZone]
    safe_margin_ratio: float = Field(default=0.05, ge=0.02, le=0.15)
