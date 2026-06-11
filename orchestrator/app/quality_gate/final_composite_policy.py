"""Failure reducer for final composite quality reports."""

from __future__ import annotations

from orchestrator.app.quality_gate.final_composite_schemas import CompositeFailureType, CompositeRevisionAction


ACTION_BY_FAILURE: dict[str, CompositeRevisionAction] = {
    "generic_copy": "rewrite_copy",
    "headline_too_long": "shorten_copy",
    "copy_clipping": "shorten_copy",
    "product_overlap": "retry_layout",
    "face_hand_overlap": "retry_layout",
    "alignment_error": "retry_layout",
    "safe_margin_violation": "retry_layout",
    "low_contrast": "retry_text_style",
    "weak_headline_hierarchy": "retry_text_style",
    "font_fallback": "retry_text_style",
    "cta_dominance": "reduce_cta_emphasis",
    "plate_too_large": "reduce_cta_emphasis",
    "background_has_no_text_space": "regenerate_background",
    "visual_clutter": "regenerate_background",
    "provider_unavailable": "manual_review",
    "final_image_contract_mismatch": "manual_review",
    "business_fit_mismatch": "manual_review",
    "brand_fit_mismatch": "manual_review",
    "commercial_viability_low": "manual_review",
    "expected_copy_mismatch": "retry_text_style",
    "unexpected_text": "regenerate_background",
}

ACTION_ORDER: list[CompositeRevisionAction] = [
    "shorten_copy",
    "retry_text_style",
    "reduce_cta_emphasis",
    "retry_layout",
    "rewrite_copy",
    "regenerate_background",
    "manual_review",
    "reject",
]


def actions_for_failures(failures: list[CompositeFailureType]) -> list[CompositeRevisionAction]:
    actions: list[CompositeRevisionAction] = []
    for failure in failures:
        action = ACTION_BY_FAILURE.get(failure, "manual_review")
        if action not in actions:
            actions.append(action)
    return sorted(actions, key=lambda action: ACTION_ORDER.index(action) if action in ACTION_ORDER else len(ACTION_ORDER))


def primary_action_for_failures(failures: list[CompositeFailureType]) -> CompositeRevisionAction:
    actions = actions_for_failures(failures)
    return actions[0] if actions else "none"


def status_for_action(action: CompositeRevisionAction, *, confidence: float = 1.0) -> str:
    if action == "none":
        return "pass"
    if action in {"manual_review"} or confidence < 0.35:
        return "manual_review"
    if action == "reject":
        return "reject"
    return "revise"
