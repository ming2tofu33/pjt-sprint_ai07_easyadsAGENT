"""Deterministic copy/visual intent policy."""

from __future__ import annotations

from typing import Any

from orchestrator.app.schemas.llm_marketing import MarketingContext
from orchestrator.app.schemas.text_layout import CopyVisualIntent


CONVERSION_GOALS = {"reservation", "reservation_cta", "inquiry", "purchase", "discount_event", "consultation", "visit"}


def resolve_copy_visual_intent(
    context: MarketingContext | dict[str, Any] | None,
    *,
    selected_reference_template: dict[str, Any] | None = None,
) -> CopyVisualIntent:
    context = context if isinstance(context, MarketingContext) else MarketingContext(**(context or {}))
    goal = str(context.promotion_goal or "").lower()
    business = str(context.business_type or "").lower()
    ref = selected_reference_template or {}
    layout_hint = ref.get("layout_hint")
    typography_hint = ref.get("typography_hint")
    ref_text = " ".join(str(value).lower() for value in [layout_hint, typography_hint, ref.get("title"), *(ref.get("style_keywords") or [])])

    if business in {"macaron", "cafe"} and (goal in {"menu_discovery", "new_launch"} or "editorial" in ref_text or "serif" in ref_text):
        return CopyVisualIntent(
            hierarchy="editorial_product",
            headline_emphasis="large_elegant",
            body_density="low",
            cta_visibility="optional",
            cta_style="text_link",
            preferred_alignment="left",
            typography_mood="premium_serif",
            plate_policy="none",
            product_text_relationship="side_by_side",
            reference_layout_hint=layout_hint,
            reference_typography_hint=typography_hint,
            reasoning_summary="Editorial menu/product showcase with low copy density.",
        )

    if any(token in goal for token in CONVERSION_GOALS):
        return CopyVisualIntent(
            hierarchy="conversion",
            headline_emphasis="large_bold",
            body_density="medium",
            cta_visibility="required",
            cta_style="pill_button" if business not in {"beauty_nail", "beauty_hair", "beauty_skincare"} else "small_label",
            preferred_alignment="left",
            typography_mood="clean_sans",
            plate_policy="cta_only",
            product_text_relationship="text_over_negative_space",
            reference_layout_hint=layout_hint,
            reference_typography_hint=typography_hint,
            reasoning_summary="Conversion-oriented ad with explicit CTA.",
        )

    if "premium" in ref_text or context.brand_tone == "premium":
        return CopyVisualIntent(
            hierarchy="minimal_premium",
            headline_emphasis="minimal",
            body_density="low",
            cta_visibility="hidden",
            cta_style="none",
            preferred_alignment="adaptive",
            typography_mood="premium_serif",
            plate_policy="none",
            product_text_relationship="centered_minimal",
            reference_layout_hint=layout_hint,
            reference_typography_hint=typography_hint,
            reasoning_summary="Minimal premium ad with hidden CTA.",
        )

    return CopyVisualIntent(
        hierarchy="information_first",
        headline_emphasis="medium_balanced",
        body_density="medium",
        cta_visibility="optional",
        cta_style="small_label",
        preferred_alignment="adaptive",
        typography_mood="clean_sans",
        plate_policy="subtle",
        product_text_relationship="text_over_negative_space",
        reference_layout_hint=layout_hint,
        reference_typography_hint=typography_hint,
        reasoning_summary="Default balanced information hierarchy.",
    )
