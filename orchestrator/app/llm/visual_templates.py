"""Deterministic visual templates for ImagePrompt v2."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class VisualTemplate:
    template_id: str
    business_types: list[str]
    ad_formats: list[str]
    style_profiles: list[str]
    main_subject_zone: str
    reserved_text_area_policy: str
    composition: str
    lighting: str
    background_style: str
    color_palette_hint: list[str]
    negative_prompt_additions: list[str]
    prompt_phrases: list[str]


def get_visual_templates() -> list[VisualTemplate]:
    return [
        VisualTemplate(
            template_id="cafe_dessert_soft_premium",
            business_types=["cafe", "dessert", "bakery"],
            ad_formats=["instagram_feed", "instagram_story", "poster"],
            style_profiles=["premium", "warm", "emotional", "clean"],
            main_subject_zone="center lower third",
            reserved_text_area_policy="upper or lower negative space kept low contrast",
            composition="fresh fruit or drink product hero with minimal props",
            lighting="warm natural daylight",
            background_style="soft cream cafe dessert background",
            color_palette_hint=["#F6E7D8", "#FFF8EF", "#D98F73"],
            negative_prompt_additions=["busy cafe signage", "printed menu text"],
            prompt_phrases=["premium but friendly cafe mood", "clean negative space", "minimal props"],
        ),
        VisualTemplate(
            template_id="restaurant_bbq_warm_grill",
            business_types=["restaurant", "bbq", "korean_food", "meat_restaurant"],
            ad_formats=["instagram_feed", "banner", "flyer", "poster"],
            style_profiles=["premium", "bold", "warm", "trendy"],
            main_subject_zone="center table hero away from text zones",
            reserved_text_area_policy="clear uncluttered text area on one side",
            composition="appetizing food hero on a warm grill table",
            lighting="warm grill highlights with appetizing contrast",
            background_style="dark warm Korean restaurant background",
            color_palette_hint=["#2A1B16", "#A8572A", "#F4C27A"],
            negative_prompt_additions=["smoke covering text area", "cluttered tableware"],
            prompt_phrases=["Korean restaurant mood", "no clutter in text area", "warm grill table"],
        ),
        VisualTemplate(
            template_id="beauty_salon_clean_pastel",
            business_types=["beauty", "salon", "hair_salon", "nail", "skincare"],
            ad_formats=["instagram_feed", "instagram_story", "poster"],
            style_profiles=["clean", "premium", "emotional", "cute"],
            main_subject_zone="center right service mood",
            reserved_text_area_policy="ample bright text space with low texture",
            composition="minimal elegant product or service mood composition",
            lighting="clean bright studio lighting",
            background_style="soft pastel beauty studio background",
            color_palette_hint=["#F8DDE6", "#F7F3FF", "#C9D7F2"],
            negative_prompt_additions=["busy salon signage", "mirror text"],
            prompt_phrases=["minimal elegant composition", "soft pastel background", "ample text space"],
        ),
        VisualTemplate(
            template_id="generic_clean_ad_background",
            business_types=["*"],
            ad_formats=["*"],
            style_profiles=["*"],
            main_subject_zone="center away from text zones",
            reserved_text_area_policy="clear reserved text area, no text, no logo, no watermark",
            composition="simple clean advertising background",
            lighting="clean commercial lighting",
            background_style="neutral commercial background",
            color_palette_hint=["#F5F5F5", "#FFFFFF", "#D1D5DB"],
            negative_prompt_additions=["visual clutter", "signage"],
            prompt_phrases=["clean advertising background", "simple composition", "clear reserved text area"],
        ),
    ]


def select_visual_template(
    business_type: str | None,
    ad_format: str | None,
    style_profile: str | None,
    selected_reference_template: dict[str, Any] | None = None,
) -> VisualTemplate:
    reference_keywords = " ".join(str(item) for item in (selected_reference_template or {}).get("style_keywords", []))
    haystack = " ".join(str(value or "") for value in [business_type, ad_format, style_profile, reference_keywords]).lower()
    templates = get_visual_templates()
    for template in templates:
        if template.template_id == "generic_clean_ad_background":
            continue
        if any(token != "*" and token.lower() in haystack for token in template.business_types):
            return template
    return templates[-1]

