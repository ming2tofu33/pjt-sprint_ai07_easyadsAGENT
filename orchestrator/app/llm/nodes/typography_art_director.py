"""Deterministic/guarded typography art direction selection."""

from __future__ import annotations

import os
from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator

from orchestrator.app.rendering.font_catalog import font_catalog_for_llm, list_font_families, nearest_available_weight
from orchestrator.app.rendering.font_pairings import PRESETS, get_pairing_preset
from orchestrator.app.schemas.text_layout import TypographyLanguagePolicy


PresetId = Literal["editorial_serif_sans", "soft_beauty", "clean_modern", "rounded_friendly", "bold_event", "english_editorial", "bilingual_editorial", "hanja_safe_serif"]


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
    language_policy: TypographyLanguagePolicy = Field(default_factory=TypographyLanguagePolicy)
    headline_script: Literal["hangul", "latin", "mixed", "hanja"] = "hangul"
    body_script: Literal["hangul", "latin", "mixed", "hanja"] = "hangul"
    cta_script: Literal["hangul", "latin", "mixed"] = "hangul"
    latin_display_family_id: str | None = None
    korean_fallback_family_id: str | None = None
    hanja_fallback_family_id: str | None = None
    rationale_summary: str = ""
    confidence: float = Field(default=0.75, ge=0.0, le=1.0)

    @model_validator(mode="after")
    def validate_allowlist(self):
        allowed = set(list_font_families())
        families = {self.headline_family_id, self.body_family_id, self.cta_family_id}
        for optional in (self.latin_display_family_id, self.korean_fallback_family_id, self.hanja_fallback_family_id):
            if optional:
                families.add(optional)
        unknown = families - allowed
        if unknown:
            raise ValueError(f"unknown font family: {sorted(unknown)}")
        if len({self.headline_family_id, self.body_family_id, self.cta_family_id}) > 2:
            preset = get_pairing_preset(self.preset_id)
            self.headline_family_id = preset.headline.family_id
            self.body_family_id = preset.body.family_id
            self.cta_family_id = preset.cta.family_id
        self.headline_weight = nearest_available_weight(self.headline_family_id, self.headline_weight)
        self.body_weight = nearest_available_weight(self.body_family_id, self.body_weight)
        self.cta_weight = nearest_available_weight(self.cta_family_id, self.cta_weight)
        if self.preset_id in {"editorial_serif_sans", "bilingual_editorial", "english_editorial"} and self.cta_treatment == "button":
            self.cta_treatment = "editorial_underline"
        if self.headline_script != "latin" and self.headline_family_id == "cormorant_garamond":
            self.headline_family_id = self.korean_fallback_family_id or "ridi_batang"
            self.headline_weight = nearest_available_weight(self.headline_family_id, self.headline_weight)
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
    english_editorial = _allows_english_editorial(business=business, mood=mood, hierarchy=hierarchy)
    if english_editorial:
        preset_id = "bilingual_editorial"
    elif "beauty" in business or "nail" in business or "hair" in business or "spa" in business:
        preset_id = "soft_beauty"
    elif "event" in goal or "discount" in goal:
        preset_id = "bold_event"
    elif "reservation" in goal:
        preset_id = "clean_modern"
    elif "rounded" in mood or "cafe" in business:
        preset_id = "rounded_friendly"
    else:
        preset_id = "clean_modern"

    preset = PRESETS[preset_id]
    cta_treatment: Literal["none", "text_link", "editorial_underline", "small_chip", "button"]
    if cta_visibility == "hidden" or goal == "brand_awareness":
        cta_treatment = "none"
    elif preset_id in {"editorial_serif_sans", "bilingual_editorial", "english_editorial"} or goal == "menu_discovery":
        cta_treatment = "editorial_underline"
    elif goal in {"reservation", "consultation"}:
        cta_treatment = "small_chip"
    elif "event" in goal or "discount" in goal:
        cta_treatment = "button"
    else:
        cta_treatment = "text_link"

    language_policy = TypographyLanguagePolicy(
        primary_locale="mixed" if english_editorial else "ko-KR",
        headline_language_mode="english" if english_editorial else "auto",
        body_language_mode="korean",
        cta_language_mode="korean",
        allow_english_display_headline=True,
        allow_english_brand_label=True,
        allow_hanja=preset_id == "hanja_safe_serif",
    )
    return TypographyArtDirection(
        preset_id=preset_id,
        headline_family_id=preset.headline.family_id,
        body_family_id=preset.body.family_id,
        cta_family_id=preset.cta.family_id,
        headline_weight=preset.headline.weight,
        body_weight=preset.body.weight,
        cta_weight=preset.cta.weight,
        headline_scale="display_large" if preset_id in {"editorial_serif_sans", "bilingual_editorial", "english_editorial"} else "headline_large",
        body_scale="body_small" if preset_id in {"editorial_serif_sans", "bilingual_editorial", "english_editorial", "soft_beauty"} else "body_medium",
        headline_tracking="tight" if preset_id in {"editorial_serif_sans", "bilingual_editorial", "english_editorial"} else "normal",
        body_tracking="normal",
        headline_leading="compact" if preset_id in {"editorial_serif_sans", "bilingual_editorial", "english_editorial"} else "normal",
        body_leading="relaxed" if preset_id in {"editorial_serif_sans", "bilingual_editorial", "english_editorial", "soft_beauty"} else "normal",
        color_strategy="adaptive",
        overlay_strategy="none",
        cta_treatment=cta_treatment,
        decorative_rule="short_horizontal_rule" if preset_id in {"editorial_serif_sans", "bilingual_editorial", "english_editorial"} else "none",
        language_policy=language_policy,
        headline_script="latin" if english_editorial else "hangul",
        body_script="hangul",
        cta_script="hangul",
        latin_display_family_id="cormorant_garamond" if english_editorial else None,
        korean_fallback_family_id="ridi_batang" if english_editorial else None,
        hanja_fallback_family_id="noto_serif_cjk_kr",
        rationale_summary="Deterministic allowlisted typography direction; API calls disabled unless EASYADS_TYPOGRAPHY_ACTUAL=1.",
        confidence=0.78 if os.getenv("EASYADS_TYPOGRAPHY_ACTUAL") != "1" else 0.85,
    )


def _allows_english_editorial(*, business: str, mood: str, hierarchy: str) -> bool:
    editorial = "editorial" in mood or "premium" in mood or "editorial_product" in hierarchy or "minimal_premium" in hierarchy
    category = any(token in business for token in ["macaron", "dessert", "cafe", "fashion", "beauty", "lifestyle", "nail"])
    return editorial and category
