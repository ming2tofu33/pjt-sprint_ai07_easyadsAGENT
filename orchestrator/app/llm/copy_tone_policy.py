"""Deterministic copy tone policies by business type."""

from __future__ import annotations

import re
from copy import deepcopy
from typing import Any

POLICIES: dict[str, dict[str, Any]] = {
    "cafe": {
        "policy_id": "cafe_v1",
        "business_type": "cafe",
        "headline_max_chars": 18,
        "subcopy_max_chars": 34,
        "cta_max_chars": 12,
        "preferred_tone": ["warm", "seasonal", "fresh", "premium"],
        "avoid_terms": ["\uc5ed\ub300\uae09", "\ubb34\uc870\uac74", "\ub300\ubc15", "\ucd5c\uc800\uac00", "\ubbf8\uce5c \ud560\uc778"],
        "cta_candidates": ["\uc9c0\uae08 \ub9cc\ub098\ubcf4\uae30", "\uc624\ub298\uc758 \uba54\ub274", "\uc2e0\uba54\ub274 \ubcf4\uae30"],
        "promotion_style": "seasonal_new_menu",
        "visual_fit_notes": ["soft product hero", "clean text area", "avoid discount flyer mood"],
    },
    "restaurant_bbq": {
        "policy_id": "restaurant_bbq_v1",
        "business_type": "restaurant_bbq",
        "headline_max_chars": 18,
        "subcopy_max_chars": 34,
        "cta_max_chars": 12,
        "preferred_tone": ["warm", "appetizing", "premium", "visit_oriented"],
        "avoid_terms": ["\ucd08\ud2b9\uac00", "\ubb34\ud55c \ub300\ubc15", "\uc2f8\ub2e4", "\uac00\uc131\ube44 \ub05d\ud310\uc655", "\ubc30 \ud130\uc9c0\ub294"],
        "cta_candidates": ["\uc9c0\uae08 \uc608\uc57d\ud558\uae30", "\uc608\uc57d \ubb38\uc758\ud558\uae30", "\ud68c\uc2dd \uc608\uc57d\ud558\uae30"],
        "promotion_style": "reservation_visit",
        "visual_fit_notes": ["warm grill mood", "food hero", "clear reservation CTA"],
    },
    "beauty_skincare": {
        "policy_id": "beauty_skincare_v1",
        "business_type": "beauty_skincare",
        "headline_max_chars": 18,
        "subcopy_max_chars": 34,
        "cta_max_chars": 12,
        "preferred_tone": ["clean", "trustworthy", "premium", "calm"],
        "avoid_terms": ["100% \uac1c\uc120", "\uc989\uc2dc \ud6a8\uacfc", "\uae30\uc801", "\uc644\uce58", "\ubb34\uc870\uac74 \uc608\ubed0\uc9d0"],
        "cta_candidates": ["\uc0c1\ub2f4 \uc608\uc57d\ud558\uae30", "\uc608\uc57d \ubb38\uc758\ud558\uae30", "\ucf00\uc5b4 \uc0c1\ub2f4\ud558\uae30"],
        "promotion_style": "consultation_trust",
        "visual_fit_notes": ["clean bright studio", "soft skin-care mood", "avoid medical claims"],
    },
    "beauty_hair": {
        "policy_id": "beauty_hair_v1",
        "business_type": "beauty_hair",
        "headline_max_chars": 18,
        "subcopy_max_chars": 34,
        "cta_max_chars": 12,
        "preferred_tone": ["stylish", "personal", "premium"],
        "avoid_terms": ["100% \uac1c\uc120", "\uc989\uc2dc \ud6a8\uacfc", "\uae30\uc801", "\uc644\uce58", "\ubb34\uc870\uac74 \uc608\ubed0\uc9d0"],
        "cta_candidates": ["\uc608\uc57d \uc0c1\ub2f4\ud558\uae30", "\uc2a4\ud0c0\uc77c \uc0c1\ub2f4\ud558\uae30", "\ud5e4\uc5b4 \uc0c1\ub2f4\ud558\uae30"],
        "promotion_style": "style_consultation",
        "visual_fit_notes": ["hair/salon cue", "personal consultation", "avoid generic skincare copy"],
    },
    "beauty_nail": {
        "policy_id": "beauty_nail_v1",
        "business_type": "beauty_nail",
        "headline_max_chars": 18,
        "subcopy_max_chars": 34,
        "cta_max_chars": 12,
        "preferred_tone": ["stylish", "delicate", "mood"],
        "avoid_terms": ["100% \uac1c\uc120", "\uc989\uc2dc \ud6a8\uacfc", "\uae30\uc801", "\uc644\uce58", "\ubb34\uc870\uac74 \uc608\ubed0\uc9d0"],
        "cta_candidates": ["\ub514\uc790\uc778 \uc0c1\ub2f4\ud558\uae30", "\uc608\uc57d \ubb38\uc758\ud558\uae30", "\ubb34\ub4dc \uc0c1\ub2f4"],
        "promotion_style": "design_consultation",
        "visual_fit_notes": ["hand/nail detail", "small premium composition", "clean text area"],
    },
    "beauty_spa": {
        "policy_id": "beauty_spa_v1",
        "business_type": "beauty_spa",
        "headline_max_chars": 18,
        "subcopy_max_chars": 34,
        "cta_max_chars": 12,
        "preferred_tone": ["calm", "wellness", "soft", "premium"],
        "avoid_terms": ["100% \uac1c\uc120", "\uc989\uc2dc \ud6a8\uacfc", "\uae30\uc801", "\uc644\uce58", "\ubb34\uc870\uac74 \uc608\ubed0\uc9d0"],
        "cta_candidates": ["\uc608\uc57d \ubb38\uc758\ud558\uae30", "\ucf00\uc5b4 \uc608\uc57d\ud558\uae30", "\uc0c1\ub2f4 \uc608\uc57d\ud558\uae30"],
        "promotion_style": "wellness_booking",
        "visual_fit_notes": ["soft wellness tone", "quiet premium mood", "avoid medical effect claims"],
    },
    "generic": {
        "policy_id": "generic_v1",
        "business_type": "generic",
        "headline_max_chars": 18,
        "subcopy_max_chars": 34,
        "cta_max_chars": 12,
        "preferred_tone": ["clear", "premium", "direct"],
        "avoid_terms": ["\ub300\ubc15", "\uc5ed\ub300\uae09", "\ubb34\uc870\uac74", "\ucd08\ud2b9\uac00"],
        "cta_candidates": ["\uc790\uc138\ud788 \ubcf4\uae30", "\ubb38\uc758\ud558\uae30", "\uc608\uc57d\ud558\uae30"],
        "promotion_style": "clear_action",
        "visual_fit_notes": ["clear message", "clean layout", "avoid low-cost flyer mood"],
    },
}

ALIASES = {
    "restaurant": "restaurant_bbq",
    "bbq": "restaurant_bbq",
    "meat_restaurant": "restaurant_bbq",
    "korean_food": "restaurant_bbq",
    "beauty": "beauty_skincare",
    "salon": "beauty_skincare",
    "skincare": "beauty_skincare",
    "hair_salon": "beauty_hair",
    "hair": "beauty_hair",
    "nail": "beauty_nail",
    "spa": "beauty_spa",
    "dessert": "cafe",
    "bakery": "cafe",
}


def get_copy_tone_policy(business_type: str | None) -> dict[str, Any]:
    key = (business_type or "generic").strip().lower()
    key = ALIASES.get(key, key)
    return deepcopy(POLICIES.get(key, POLICIES["generic"]))


def normalize_copy_for_business(copy: dict[str, Any], business_type: str | None, mode: str = "generated") -> dict[str, Any]:
    policy = get_copy_tone_policy(business_type)
    original = {"headline": copy.get("headline") or "", "subcopy": copy.get("subcopy") or "", "cta": copy.get("cta") or ""}
    warnings: list[str] = []
    applied: list[str] = []
    if mode == "custom_input" or copy.get("mode") == "custom_input":
        quality = score_copy_visual_fit(original, business_type, copy.get("visual_metadata"))
        quality["warnings"] = [*quality.get("warnings", []), "custom_input_not_rewritten"]
        return {"normalized_copy": original, "quality_score": quality["quality_score"], "warnings": quality["warnings"], "policy_id": policy["policy_id"], "applied_rules": []}

    normalized = {
        "headline": _clean_text(original["headline"], policy["avoid_terms"], policy["headline_max_chars"], warnings, applied),
        "subcopy": _clean_text(original["subcopy"], policy["avoid_terms"], policy["subcopy_max_chars"], warnings, applied),
        "cta": _normalize_cta(original["cta"], policy, warnings, applied),
    }
    quality = score_copy_visual_fit(normalized, business_type, copy.get("visual_metadata"))
    return {
        "normalized_copy": normalized,
        "quality_score": quality["quality_score"],
        "warnings": sorted(set([*warnings, *quality.get("warnings", [])])),
        "policy_id": policy["policy_id"],
        "applied_rules": sorted(set(applied)),
    }


def score_copy_visual_fit(copy: dict[str, Any], business_type: str | None, visual_metadata: dict[str, Any] | None = None) -> dict[str, Any]:
    policy = get_copy_tone_policy(business_type)
    joined = " ".join(str(copy.get(key) or "") for key in ("headline", "subcopy", "cta", "promotion"))
    warnings: list[str] = []
    score = 1.0
    for term in policy["avoid_terms"]:
        if term in joined:
            score -= 0.14
            warnings.append("avoid_term_detected")
            break
    if "!!" in joined or "!!!" in joined:
        score -= 0.08
        warnings.append("excessive_punctuation")
    if len(str(copy.get("headline") or "")) > policy["headline_max_chars"]:
        score -= 0.07
        warnings.append("headline_too_long")
    cta = str(copy.get("cta") or "")
    if cta and all(candidate != cta for candidate in policy["cta_candidates"]):
        score -= 0.04
        warnings.append("cta_not_policy_preferred")
    visual_text = " ".join(str(value).lower() for value in (visual_metadata or {}).values())
    if business_type and visual_text and _canonical_business(business_type) not in visual_text:
        warnings.append("visual_business_fit_needs_manual_review")
    return {"quality_score": round(max(0.0, min(1.0, score)), 2), "warnings": sorted(set(warnings)), "policy_id": policy["policy_id"]}


def _clean_text(text: str, avoid_terms: list[str], max_chars: int, warnings: list[str], applied: list[str]) -> str:
    original = str(text or "")
    value = re.sub(r"\s+", " ", original).strip()
    value = re.sub(r"!{2,}", "!", value)
    if value != original:
        applied.append("normalized_spacing_or_punctuation")
    for term in avoid_terms:
        if term in value:
            warnings.append("avoid_term_detected")
    if len(value) > max_chars:
        warnings.append("copy_exceeds_policy_length")
    return value


def _normalize_cta(text: str, policy: dict[str, Any], warnings: list[str], applied: list[str]) -> str:
    original = str(text or "")
    had_avoid_term = any(term in original for term in policy["avoid_terms"])
    value = _clean_text(original, policy["avoid_terms"], policy["cta_max_chars"], warnings, applied)
    if had_avoid_term:
        warnings.append("cta_avoid_term_detected")
    if not value:
        if had_avoid_term:
            warnings.append("cta_empty_after_quality_check")
        applied.append("selected_policy_cta")
        return policy["cta_candidates"][0]
    return value


def _canonical_business(value: str) -> str:
    return get_copy_tone_policy(value)["business_type"].split("_")[0]
