"""Bind copy and marketing context to deterministic typography style specs."""

from __future__ import annotations

from typing import Any

from orchestrator.app.llm.copy_visual_intent import resolve_copy_visual_intent
from orchestrator.app.schemas.llm_marketing import MarketingContext
from orchestrator.app.schemas.text_layout import CopyVisualIntent, StyleProfile, TextStyleSpec, TypographyRule


TYPOGRAPHY_BY_PROFILE: dict[StyleProfile, TypographyRule] = {
    "cute": TypographyRule(
        headline_font="BMJUA",
        body_font="Pretendard",
        headline_weight=800,
        body_weight=500,
        headline_size_ratio=0.085,
        body_size_ratio=0.038,
        letter_spacing_em=0.0,
        line_height_em=1.12,
        primary_color="#FF6B9D",
        accent_color="#FFD93D",
        text_color_on_light="#2B1B2D",
        text_color_on_dark="#FFFFFF",
        default_overlay="sticker_badge",
        use_text_plate=True,
        plate_style="rounded_badge",
    ),
    "premium": TypographyRule(
        headline_font="RIDIBatang",
        body_font="MaruBuri",
        headline_weight=600,
        body_weight=400,
        headline_size_ratio=0.060,
        body_size_ratio=0.032,
        letter_spacing_em=0.05,
        line_height_em=1.20,
        primary_color="#2B2118",
        accent_color="#B58A4A",
        text_color_on_light="#2B2118",
        text_color_on_dark="#FFFFFF",
        default_overlay="plain",
        use_text_plate=False,
    ),
    "clean": TypographyRule(
        headline_font="NotoSansKR",
        body_font="NotoSansKR",
        headline_weight=700,
        body_weight=400,
        headline_size_ratio=0.065,
        body_size_ratio=0.034,
        primary_color="#1F2937",
        accent_color="#3B82F6",
        text_color_on_light="#111827",
        text_color_on_dark="#FFFFFF",
        default_overlay="drop_shadow",
        use_text_plate=False,
    ),
    "trendy": TypographyRule(
        headline_font="GmarketSans",
        body_font="Pretendard",
        headline_weight=900,
        body_weight=500,
        headline_size_ratio=0.078,
        body_size_ratio=0.036,
        letter_spacing_em=0.01,
        line_height_em=1.10,
        primary_color="#111827",
        accent_color="#00D1FF",
        text_color_on_light="#111827",
        text_color_on_dark="#FFFFFF",
        default_overlay="gradient_panel",
        use_text_plate=True,
        plate_style="contrast_panel",
    ),
    "emotional": TypographyRule(
        headline_font="MaruBuri",
        body_font="MaruBuri",
        headline_weight=700,
        body_weight=400,
        headline_size_ratio=0.070,
        body_size_ratio=0.036,
        primary_color="#3A2E2A",
        accent_color="#E85D75",
        text_color_on_light="#3A2E2A",
        text_color_on_dark="#FFFFFF",
        default_overlay="drop_shadow",
        use_text_plate=False,
    ),
    "event": TypographyRule(
        headline_font="BMDOHYEON",
        body_font="SCDream",
        headline_weight=900,
        body_weight=600,
        headline_size_ratio=0.082,
        body_size_ratio=0.038,
        primary_color="#E11D48",
        accent_color="#FACC15",
        text_color_on_light="#111827",
        text_color_on_dark="#FFFFFF",
        default_overlay="solid_panel",
        use_text_plate=True,
        plate_style="event_plate",
    ),
}


def text_style_binder_node(state: dict[str, Any]) -> dict[str, Any]:
    context = _context_to_model(state.get("context"))
    intent = CopyVisualIntent(**(state.get("copy_visual_intent") or resolve_copy_visual_intent(context, selected_reference_template=state.get("selected_reference_template")).model_dump()))
    profile = profile_for_intent(intent, infer_style_profile(context.brand_tone, context.promotion_goal))
    typography = TYPOGRAPHY_BY_PROFILE[profile].model_copy(deep=True)
    if intent.plate_policy == "none":
        typography.use_text_plate = False
        typography.default_overlay = "plain"
    elif intent.plate_policy == "cta_only":
        typography.use_text_plate = False
        typography.default_overlay = "drop_shadow"
    if intent.typography_mood in {"premium_serif", "editorial_mixed"}:
        typography.headline_font = "RIDIBatang"
        typography.body_font = "MaruBuri"
    spec = TextStyleSpec(
        profile=profile,
        typography=typography,
        role_styles={
            "cta": {"visibility": intent.cta_visibility, "style": intent.cta_style, "plate_policy": intent.plate_policy},
            "reference_layout_hint": intent.reference_layout_hint,
            "reference_typography_hint": intent.reference_typography_hint,
        },
    )
    return {
        "text_style_spec": spec.model_dump(),
        "copy_visual_intent": intent.model_dump(),
        "current_brief": {**state.get("current_brief", {}), "text_style_ready": True},
        "status": "planning_format",
    }


def _context_to_model(context: dict[str, Any] | MarketingContext | None) -> MarketingContext:
    if isinstance(context, MarketingContext):
        return context
    if isinstance(context, dict):
        return MarketingContext(**context)
    return MarketingContext()


def profile_for_intent(intent: CopyVisualIntent, fallback: StyleProfile) -> StyleProfile:
    if intent.typography_mood in {"premium_serif", "editorial_mixed"}:
        return "premium"
    if intent.typography_mood == "rounded_friendly":
        return "cute"
    if intent.typography_mood == "bold_promo":
        return "event"
    return fallback if fallback in {"clean", "premium", "cute", "event", "trendy", "emotional"} else "clean"


def infer_style_profile(brand_tone: str | None, promotion_goal: str | None) -> StyleProfile:
    tone = (brand_tone or "").lower()
    if "cute" in tone or "귀여" in tone:
        return "cute"
    if "premium" in tone or "고급" in tone:
        return "premium"
    if "clean" in tone or "깔끔" in tone:
        return "clean"
    if "trendy" in tone or "트렌디" in tone or "힙" in tone:
        return "trendy"
    if promotion_goal in {"discount_event", "event"}:
        return "event"
    return "emotional"
