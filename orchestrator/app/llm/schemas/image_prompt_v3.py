from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


BusinessType = Literal[
    "cafe",
    "restaurant_bbq",
    "restaurant",
    "beauty_skincare",
    "beauty_hair",
    "beauty_nail",
    "beauty_spa",
    "generic",
]

AdFormat = Literal[
    "instagram_feed",
    "instagram_story",
    "poster",
    "banner",
    "generic",
]

CopyAreaPlacement = Literal[
    "left",
    "right",
    "top",
    "bottom",
    "center",
    "upper_left",
    "upper_right",
    "lower_left",
    "lower_right",
]

CompositionArchetype = Literal[
    "subject_right_copy_left",
    "subject_left_copy_right",
    "subject_bottom_copy_top",
    "center_subject_surrounding_space",
    "product_tabletop_negative_space",
    "portrait_right_copy_left",
    "generic_clean_ad_background",
]


class ScenePlan(BaseModel):
    business_type: BusinessType = "generic"
    ad_format: AdFormat = "instagram_feed"
    product_or_service: str = ""
    target_customer: str | None = None
    ad_goal: str | None = None
    desired_mood: list[str] = Field(default_factory=list)
    realism_level: Literal["realistic", "premium_realistic", "studio_realistic"] = "premium_realistic"
    primary_subject: str
    secondary_props: list[str] = Field(default_factory=list)
    composition_archetype: CompositionArchetype = "generic_clean_ad_background"
    reserved_copy_area: CopyAreaPlacement = "left"
    expected_overlay_position: CopyAreaPlacement = "left"
    background_density: Literal["minimal", "moderate", "rich"] = "moderate"
    forbidden_visual_elements: list[str] = Field(default_factory=list)
    fake_text_risk_level: Literal["low", "medium", "high"] = "medium"
    reference_alignment_priority: Literal["low", "medium", "high"] = "medium"
    notes: list[str] = Field(default_factory=list)


class PromptQualityPolicy(BaseModel):
    no_text_policy: str
    safe_area_policy: str
    brand_safety_policy: str
    stock_like_risk_policy: str
    tacky_visual_risk_policy: str
    business_fit_policy: str
    fake_text_negative_terms: list[str] = Field(default_factory=list)
    positive_safe_area_terms: list[str] = Field(default_factory=list)
    composition_constraints: list[str] = Field(default_factory=list)


class EnginePromptAdapterOutput(BaseModel):
    engine: Literal["gpt_image_1", "gpt_image_2", "sd35_large", "flux", "flux2_klein_4b"]
    prompt: str
    negative_prompt: str | None = None
    engine_fit_score: float = 1.0
    warnings: list[str] = Field(default_factory=list)
    metadata: dict = Field(default_factory=dict)
