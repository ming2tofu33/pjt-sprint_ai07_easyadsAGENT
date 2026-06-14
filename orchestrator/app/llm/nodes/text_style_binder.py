"""Bind copy and marketing context to deterministic typography style specs."""

from __future__ import annotations

from typing import Any

from orchestrator.app.graph.state import read_model
from orchestrator.app.llm.copy_visual_intent import resolve_copy_visual_intent
from orchestrator.app.llm.nodes.typography_art_director import select_typography_art_direction
from orchestrator.app.schemas.llm_marketing import MarketingContext
from orchestrator.app.schemas.text_layout import CopyVisualIntent, StyleProfile, TextStyleSpec, TypographyRoleStyle, TypographyRule


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
    intent = read_model(state, "copy_visual_intent", CopyVisualIntent, default=None) or resolve_copy_visual_intent(context, selected_reference_template=state.get("selected_reference_template"))
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
    typography = apply_intent_typography(typography, intent)
    art_direction = state.get("typography_art_direction") or select_typography_art_direction({**state, "copy_visual_intent": intent.model_dump(), "context": context.model_dump()}).model_dump()
    role_styles = build_role_styles(art_direction)
    spec = TextStyleSpec(
        profile=profile,
        typography=typography,
        headline_style=role_styles["headline"],
        body_style=role_styles["body"],
        cta_style=role_styles["cta"],
        label_style=role_styles["label"],
        price_style=role_styles["price"],
        disclaimer_style=role_styles["disclaimer"],
        font_pair_id=art_direction.get("preset_id"),
        typography_art_direction=art_direction,
        role_styles={
            "cta": {"visibility": intent.cta_visibility, "style": intent.cta_style, "plate_policy": intent.plate_policy},
            "reference_layout_hint": intent.reference_layout_hint,
            "reference_typography_hint": intent.reference_typography_hint,
            "typography_art_direction": art_direction,
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


def apply_intent_typography(typography: TypographyRule, intent: CopyVisualIntent) -> TypographyRule:
    hint = (intent.reference_typography_hint or "").lower()
    if "serif" in hint:
        typography.headline_font = "RIDIBatang"
        typography.body_font = "MaruBuri"
    elif "rounded" in hint:
        typography.headline_font = "BMJUA"
        typography.body_font = "Pretendard"
    elif "bold" in hint:
        typography.headline_weight = max(typography.headline_weight, 850)
    elif "sans" in hint:
        typography.headline_font = "Pretendard"
        typography.body_font = "Pretendard"

    if intent.headline_emphasis == "large_elegant":
        typography.headline_size_ratio = max(typography.headline_size_ratio, 0.064)
        typography.headline_weight = min(max(typography.headline_weight, 600), 760)
    elif intent.headline_emphasis == "large_bold":
        typography.headline_size_ratio = max(typography.headline_size_ratio, 0.074)
        typography.headline_weight = max(typography.headline_weight, 850)
    elif intent.headline_emphasis == "minimal":
        typography.headline_size_ratio = min(typography.headline_size_ratio, 0.052)
        typography.headline_weight = min(typography.headline_weight, 650)
    return typography


def build_role_styles(direction: dict[str, Any]) -> dict[str, TypographyRoleStyle]:
    headline_scale = str(direction.get("headline_scale") or "headline_large")
    body_scale = str(direction.get("body_scale") or "body_medium")
    cta_treatment = str(direction.get("cta_treatment") or "text_link")
    headline_ratio = {"display_large": 0.078, "display_medium": 0.068, "headline_large": 0.062, "headline_medium": 0.052}.get(headline_scale, 0.062)
    body_ratio = {"body_small": 0.030, "body_medium": 0.035}.get(body_scale, 0.034)
    cta_ratio = max(0.024, min(0.030, headline_ratio / 1.8))
    headline_tracking = {"tight": -0.01, "normal": 0.0, "open": 0.025}.get(str(direction.get("headline_tracking")), 0.0)
    body_tracking = 0.015 if direction.get("body_tracking") == "open" else 0.0
    headline_leading = 1.05 if direction.get("headline_leading") == "compact" else 1.14
    body_leading = 1.24 if direction.get("body_leading") == "relaxed" else 1.15
    overlay = "editorial_underline" if cta_treatment == "editorial_underline" else ("small_chip" if cta_treatment == "small_chip" else "none")
    if cta_treatment == "button":
        overlay = "small_chip"
    headline_family = direction.get("headline_family_id") or "noto_sans_kr"
    body_family = direction.get("body_family_id") or "noto_sans_kr"
    cta_family = direction.get("cta_family_id") or body_family
    return {
        "headline": TypographyRoleStyle(role="headline", family_id=headline_family, weight=int(direction.get("headline_weight") or 700), size_ratio=headline_ratio, min_size_ratio=headline_ratio * 0.72, max_size_ratio=headline_ratio * 1.10, letter_spacing_em=headline_tracking, line_height_em=headline_leading, text_color="#4A3A31", alignment="left", max_lines=2, overlay_treatment="none"),
        "body": TypographyRoleStyle(role="body", family_id=body_family, weight=int(direction.get("body_weight") or 400), size_ratio=body_ratio, min_size_ratio=body_ratio * 0.75, max_size_ratio=body_ratio * 1.10, letter_spacing_em=body_tracking, line_height_em=body_leading, text_color="#514941", alignment="left", max_lines=3, overlay_treatment="none"),
        "cta": TypographyRoleStyle(role="cta", family_id=cta_family, weight=int(direction.get("cta_weight") or 500), size_ratio=cta_ratio, min_size_ratio=cta_ratio * 0.80, max_size_ratio=cta_ratio * 1.10, letter_spacing_em=0.01, line_height_em=1.12, text_color="#514941", alignment="left", max_lines=1, overlay_treatment=overlay),
        "label": TypographyRoleStyle(role="brand_label", family_id=body_family, weight=500, size_ratio=0.020, min_size_ratio=0.016, max_size_ratio=0.024, letter_spacing_em=0.04, line_height_em=1.10, text_color="#514941", alignment="left", max_lines=1, overlay_treatment="none"),
        "price": TypographyRoleStyle(role="price", family_id=body_family, weight=500, size_ratio=0.034, min_size_ratio=0.026, max_size_ratio=0.040, letter_spacing_em=0.0, line_height_em=1.10, text_color="#514941", alignment="left", max_lines=1, overlay_treatment="none"),
        "disclaimer": TypographyRoleStyle(role="disclaimer", family_id=body_family, weight=400, size_ratio=0.018, min_size_ratio=0.014, max_size_ratio=0.022, letter_spacing_em=0.0, line_height_em=1.15, text_color="#514941", alignment="left", max_lines=2, overlay_treatment="none"),
    }


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
