"""Copy tone metadata for MVP copywriting nodes."""

from __future__ import annotations

from typing import Any


COPY_TONE_MAPPING: dict[str, dict[str, Any]] = {
    "restaurant": {
        "voice": "warm_appetizing",
        "keywords": ["fresh", "hearty", "shareable"],
        "cta_style": "visit_reservation",
    },
    "cafe": {
        "voice": "cozy_refreshing",
        "keywords": ["relaxing", "sweet", "daily_treat"],
        "cta_style": "visit_today",
    },
    "beauty_salon": {
        "voice": "polished_confident",
        "keywords": ["clean", "premium", "personal_care"],
        "cta_style": "book_now",
    },
    "bar": {
        "voice": "night_social",
        "keywords": ["mood", "friends", "after_hours"],
        "cta_style": "reserve_table",
    },
    "fitness": {
        "voice": "energetic_direct",
        "keywords": ["strong", "healthy", "start_now"],
        "cta_style": "trial_signup",
    },
    "academy": {
        "voice": "clear_trustworthy",
        "keywords": ["growth", "results", "confidence"],
        "cta_style": "consultation",
    },
    "flower_shop": {
        "voice": "emotional_elegant",
        "keywords": ["gift", "seasonal", "beautiful"],
        "cta_style": "order_now",
    },
    "store": {
        "voice": "friendly_practical",
        "keywords": ["new", "useful", "limited"],
        "cta_style": "shop_now",
    },
}

FALLBACK_COPY_TONE_PROFILE: dict[str, Any] = {
    "voice": "friendly_clear",
    "keywords": ["simple", "benefit", "action"],
    "cta_style": "learn_more",
}

PERSONA_TONE_HINTS: dict[str, dict[str, Any]] = {
    "college_student": {"energy": "casual", "phrase_style": "short"},
    "office_worker": {"energy": "efficient", "phrase_style": "benefit_first"},
    "young_social": {"energy": "trendy", "phrase_style": "shareable"},
    "tourist": {"energy": "welcoming", "phrase_style": "location_friendly"},
    "family_local": {"energy": "trusted", "phrase_style": "warm"},
}


def get_copy_tone_profile(business_type: str | None, target_persona: str | None) -> dict[str, Any]:
    profile = dict(COPY_TONE_MAPPING.get(business_type or "", FALLBACK_COPY_TONE_PROFILE))
    profile["business_type"] = business_type or "unknown"
    profile["target_persona"] = target_persona or "unknown"
    profile["persona_hint"] = PERSONA_TONE_HINTS.get(target_persona or "", {})
    return profile
