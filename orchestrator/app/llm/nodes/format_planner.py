"""Rule-based ad format and layout planning node."""

from __future__ import annotations

from typing import Any

from orchestrator.app.graph.state import MarketingState, context_to_model
from orchestrator.app.llm.ad_format_presets import build_ad_format_spec
from orchestrator.app.schemas.llm_marketing import LayoutSpec, TextZone, Zone


VALID_AD_FORMATS = {"instagram_feed", "instagram_story", "poster", "flyer", "banner", "product_detail"}


def format_planner_node(state: MarketingState) -> dict[str, Any]:
    context = context_to_model(state.get("context"))
    ad_format = resolve_ad_format(state)
    ad_format_spec = build_ad_format_spec(ad_format)
    layout_spec = build_layout_spec(ad_format)
    return {
        "ad_format_spec": ad_format_spec.model_dump(),
        "layout_spec": layout_spec.model_dump(),
        "current_brief": {
            **state.get("current_brief", {}),
            "requested_ad_format": ad_format_spec.ad_format,
            "planned_platform": ad_format_spec.platform,
            "ready_for_copywriting": True,
        },
        "status": "planning_format",
        "dirty_fields": [],
        "context": context.model_dump(),
    }


def resolve_ad_format(state: MarketingState) -> str:
    current_brief = state.get("current_brief", {})
    context = context_to_model(state.get("context"))
    validator_output = state.get("validator_output") or {}
    candidates = [
        current_brief.get("requested_ad_format"),
        context.extra.get("ad_format"),
        _extract_validator_ad_format(validator_output),
        current_brief.get("ad_format"),
        "instagram_feed",
    ]
    for candidate in candidates:
        if candidate in VALID_AD_FORMATS:
            return str(candidate)
    return "instagram_feed"


def _extract_validator_ad_format(validator_output: Any) -> str | None:
    if not isinstance(validator_output, dict):
        return None
    inferred = validator_output.get("inferred_ad_format")
    if isinstance(inferred, dict):
        return inferred.get("ad_format")
    return None


def build_layout_spec(ad_format: str) -> LayoutSpec:
    if ad_format == "instagram_story":
        return LayoutSpec(
            layout_type="story_vertical",
            copy_space="bottom",
            safe_area=Zone(x=0.08, y=0.08, width=0.84, height=0.84),
            text_zones=[
                TextZone(x=0.08, y=0.66, width=0.84, height=0.14, role="headline", max_chars=28),
                TextZone(x=0.10, y=0.82, width=0.80, height=0.08, role="cta", max_chars=16),
            ],
            product_zone=Zone(x=0.10, y=0.16, width=0.80, height=0.44),
            cta_zone=Zone(x=0.18, y=0.84, width=0.64, height=0.08),
            overlay_style="gradient",
            text_align="center",
            max_text_density="low",
        )
    if ad_format == "flyer":
        return LayoutSpec(
            layout_type="flyer_information",
            copy_space="right",
            safe_area=Zone(x=0.06, y=0.06, width=0.88, height=0.88),
            text_zones=[
                TextZone(x=0.54, y=0.14, width=0.36, height=0.18, role="headline", max_chars=36, align="left"),
                TextZone(x=0.54, y=0.36, width=0.36, height=0.28, role="subcopy", max_chars=72, align="left"),
                TextZone(x=0.54, y=0.70, width=0.36, height=0.10, role="cta", max_chars=20, align="left"),
            ],
            product_zone=Zone(x=0.06, y=0.14, width=0.42, height=0.60),
            cta_zone=Zone(x=0.54, y=0.70, width=0.36, height=0.10),
            overlay_style="solid_box",
            text_align="left",
            max_text_density="high",
        )
    if ad_format == "banner":
        return LayoutSpec(
            layout_type="split_text_image",
            copy_space="left",
            safe_area=Zone(x=0.04, y=0.10, width=0.92, height=0.80),
            text_zones=[
                TextZone(x=0.06, y=0.24, width=0.34, height=0.18, role="headline", max_chars=26, align="left"),
                TextZone(x=0.06, y=0.48, width=0.34, height=0.12, role="subcopy", max_chars=50, align="left"),
                TextZone(x=0.06, y=0.66, width=0.26, height=0.10, role="cta", max_chars=16, align="left"),
            ],
            product_zone=Zone(x=0.46, y=0.14, width=0.46, height=0.72),
            cta_zone=Zone(x=0.06, y=0.66, width=0.26, height=0.10),
            overlay_style="gradient",
            text_align="left",
            max_text_density="medium",
        )
    if ad_format == "product_detail":
        return LayoutSpec(
            layout_type="multi_section",
            copy_space="none",
            safe_area=Zone(x=0.05, y=0.05, width=0.90, height=0.90),
            text_zones=[
                TextZone(x=0.08, y=0.08, width=0.84, height=0.10, role="headline", max_chars=32),
                TextZone(x=0.08, y=0.76, width=0.84, height=0.12, role="cta", max_chars=20),
            ],
            product_zone=Zone(x=0.08, y=0.22, width=0.84, height=0.48),
            cta_zone=Zone(x=0.08, y=0.76, width=0.84, height=0.12),
            overlay_style="none",
            text_align="center",
            max_text_density="high",
        )
    if ad_format == "poster":
        return LayoutSpec(
            layout_type="top_headline_bottom_product",
            copy_space="bottom",
            safe_area=Zone(x=0.07, y=0.08, width=0.86, height=0.84),
            text_zones=[
                TextZone(x=0.10, y=0.10, width=0.80, height=0.16, role="headline", max_chars=30),
                TextZone(x=0.12, y=0.76, width=0.76, height=0.12, role="cta", max_chars=18),
            ],
            product_zone=Zone(x=0.12, y=0.30, width=0.76, height=0.40),
            cta_zone=Zone(x=0.12, y=0.76, width=0.76, height=0.12),
            overlay_style="gradient",
            text_align="center",
            max_text_density="medium",
        )
    return LayoutSpec(
        layout_type="single_hero",
        copy_space="bottom",
        safe_area=Zone(x=0.06, y=0.06, width=0.88, height=0.88),
        text_zones=[
            TextZone(x=0.10, y=0.66, width=0.80, height=0.14, role="headline", max_chars=28),
            TextZone(x=0.12, y=0.82, width=0.76, height=0.08, role="cta", max_chars=16),
        ],
        product_zone=Zone(x=0.10, y=0.12, width=0.80, height=0.48),
        cta_zone=Zone(x=0.12, y=0.82, width=0.76, height=0.08),
        overlay_style="gradient",
        text_align="center",
        max_text_density="medium",
    )
