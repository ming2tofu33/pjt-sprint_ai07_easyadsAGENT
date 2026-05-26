"""Ad format presets for LLM/LangGraph format planning."""

from __future__ import annotations

from orchestrator.app.schemas.llm_marketing import AdFormatSpec


AD_FORMAT_PRESETS: dict[str, dict[str, object]] = {
    "instagram_feed": {
        "platform": "instagram",
        "aspect_ratio": "1:1",
        "width": 1080,
        "height": 1080,
        "information_density": "medium",
        "visual_priority": "product_hero",
        "output_strategy": "generate_text_free_background_then_overlay",
    },
    "instagram_story": {
        "platform": "instagram",
        "aspect_ratio": "9:16",
        "width": 1080,
        "height": 1920,
        "information_density": "low",
        "visual_priority": "mood_first",
        "output_strategy": "generate_text_free_background_then_overlay",
    },
    "poster": {
        "platform": "offline",
        "aspect_ratio": "4:5",
        "width": 1080,
        "height": 1350,
        "information_density": "medium",
        "visual_priority": "product_hero",
        "output_strategy": "generate_text_free_background_then_overlay",
    },
    "flyer": {
        "platform": "offline",
        "aspect_ratio": "A4_vertical",
        "width": 1240,
        "height": 1754,
        "information_density": "high",
        "visual_priority": "information_first",
        "output_strategy": "multi_section_layout",
    },
    "banner": {
        "platform": "web",
        "aspect_ratio": "16:9",
        "width": 1600,
        "height": 900,
        "information_density": "low",
        "visual_priority": "click_conversion",
        "output_strategy": "generate_text_free_background_then_overlay",
    },
    "product_detail": {
        "platform": "naver_smartstore",
        "aspect_ratio": "4:5",
        "width": 1200,
        "height": 1500,
        "information_density": "high",
        "visual_priority": "detail_explanation",
        "output_strategy": "multi_section_layout",
    },
}


def build_ad_format_spec(ad_format: str) -> AdFormatSpec:
    preset = AD_FORMAT_PRESETS.get(ad_format)
    if preset is None:
        preset = AD_FORMAT_PRESETS["instagram_feed"]
        ad_format = "instagram_feed"
    return AdFormatSpec(ad_format=ad_format, **preset)
