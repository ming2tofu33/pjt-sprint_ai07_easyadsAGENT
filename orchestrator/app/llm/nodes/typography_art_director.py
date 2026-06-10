"""Deterministic/guarded typography art direction selection."""

from __future__ import annotations

import os
from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator

from orchestrator.app.rendering.font_catalog import font_catalog_for_llm, list_font_families, nearest_available_weight
from orchestrator.app.rendering.font_pairings import PRESETS, get_pairing_preset


PresetId = Literal["editorial_serif_sans", "soft_beauty", "clean_modern", "rounded_friendly", "bold_event", "trustworthy"]


class TypographyArtDirection(BaseModel):
    preset_id: PresetId
    headline_family_id: str
    body_family_id: str
    cta_family_id: str
    headline_weight: int = Field(..., ge=100, le=1000)
    body_weight: int = Field(..., ge=100, le=1000)
    cta_weight: int = Field(..., ge=100, le=1000)
    headline_scale: Literal["display_large", "display_medium", "headline_large", "headline_medium"]
    body_scale: Literal["body_small", "body_medium"]
    headline_tracking: Literal["tight", "normal", "open"]
    body_tracking: Literal["normal", "open"]
    headline_leading: Literal["compact", "normal"]
    body_leading: Literal["normal", "relaxed"]
    color_strategy: Literal["adaptive", "dark_on_light", "light_on_dark", "brand_dark"] = "adaptive"
    overlay_strategy: Literal["none", "soft_gradient_veil", "localized_blur", "content_fit_plate"] = "none"
    cta_treatment: Literal["none", "text_link", "editorial_underline", "small_chip", "button"] = "text_link"
    decorative_rule: Literal["none", "short_horizontal_rule", "headline_underline"] = "none"
    rationale_summary: str = ""
    confidence: float = Field(default=0.75, ge=0.0, le=1.0)

    @model_validator(mode="after")
    def validate_allowlist(self):
        allowed = set(list_font_families())
        families = {self.headline_family_id, self.body_family_id, self.cta_family_id}
        unknown = families - allowed
        if unknown:
            raise ValueError(f"unknown font family: {sorted(unknown)}")
        if len(families) > 2:
            preset = get_pairing_preset(self.preset_id)
            self.headline_family_id = preset.headline.family_id
            self.body_family_id = preset.body.family_id
            self.cta_family_id = preset.cta.family_id
        self.headline_weight = nearest_available_weight(self.headline_family_id, self.headline_weight)
        self.body_weight = nearest_available_weight(self.body_family_id, self.body_weight)
        self.cta_weight = nearest_available_weight(self.cta_family_id, self.cta_weight)
        if self.preset_id == "editorial_serif_sans" and self.cta_treatment == "button":
            self.cta_treatment = "editorial_underline"
        return self


def typography_art_direction_node(state: dict[str, Any]) -> dict[str, Any]:
    direction = select_typography_art_direction(state)
    return {
        "typography_art_direction": direction.model_dump(),
        "font_catalog_summary": font_catalog_for_llm(),
        "status": "planning_format",
    }


def select_typography_art_direction(state: dict[str, Any]) -> TypographyArtDirection:
    intent = state.get("copy_visual_intent") or {}
    context = state.get("context") or {}
    business = str(context.get("business_type") or context.get("item_or_service") or "").lower()
    goal = str(context.get("promotion_goal") or "").lower()
    mood = str(intent.get("typography_mood") or "").lower()
    hierarchy = str(intent.get("hierarchy") or "").lower()
    cta_visibility = str(intent.get("cta_visibility") or "optional")

    preset_id: PresetId
    if "macaron" in business or "editorial" in mood or "premium" in mood or "editorial_product" in hierarchy:
        preset_id = "editorial_serif_sans"
    elif "beauty" in business or "nail" in business or "hair" in business or "spa" in business:
        preset_id = "soft_beauty"
    elif "event" in goal or "discount" in goal:
        preset_id = "bold_event"
    elif "reservation" in goal:
        preset_id = "trustworthy"
    elif "rounded" in mood or "cafe" in business:
        preset_id = "rounded_friendly"
    else:
        preset_id = "clean_modern"

    preset = PRESETS[preset_id]
    cta_treatment: Literal["none", "text_link", "editorial_underline", "small_chip", "button"]
    if cta_visibility == "hidden" or goal == "brand_awareness":
        cta_treatment = "none"
    elif preset_id == "editorial_serif_sans" or goal == "menu_discovery":
        cta_treatment = "editorial_underline"
    elif goal in {"reservation", "consultation"}:
        cta_treatment = "small_chip"
    elif "event" in goal or "discount" in goal:
        cta_treatment = "button"
    else:
        cta_treatment = "text_link"

    return TypographyArtDirection(
        preset_id=preset_id,
        headline_family_id=preset.headline.family_id,
        body_family_id=preset.body.family_id,
        cta_family_id=preset.cta.family_id,
        headline_weight=preset.headline.weight,
        body_weight=preset.body.weight,
        cta_weight=preset.cta.weight,
        headline_scale="display_large" if preset_id == "editorial_serif_sans" else "headline_large",
        body_scale="body_small" if preset_id in {"editorial_serif_sans", "soft_beauty"} else "body_medium",
        headline_tracking="tight" if preset_id == "editorial_serif_sans" else "normal",
        body_tracking="normal",
        headline_leading="compact" if preset_id == "editorial_serif_sans" else "normal",
        body_leading="relaxed" if preset_id in {"editorial_serif_sans", "soft_beauty"} else "normal",
        color_strategy="adaptive",
        overlay_strategy="none",
        cta_treatment=cta_treatment,
        decorative_rule="short_horizontal_rule" if preset_id == "editorial_serif_sans" else "none",
        rationale_summary="Deterministic allowlisted typography direction; API calls disabled unless EASYADS_TYPOGRAPHY_ACTUAL=1.",
        confidence=0.78 if os.getenv("EASYADS_TYPOGRAPHY_ACTUAL") != "1" else 0.85,
    )
