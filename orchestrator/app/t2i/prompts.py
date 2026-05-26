"""Negative prompt policy for ad-oriented T2I generation."""

from __future__ import annotations

from typing import Any


COMMON_NEGATIVE_PROMPT = (
    "text, watermark, logo, signature, letters, numbers, broken typography, "
    "deformed object, low quality, blurry, artifacts, distorted food, "
    "plastic texture, oversaturated, uncanny, extra fingers, unwanted people, "
    "people where not requested"
)

INDUSTRY_NEGATIVE_PROMPTS: dict[str, str] = {
    "restaurant": (
        "raw meat distortion, gross texture, burnt food, spoiled food, "
        "dirty table, unappetizing food, rotten ingredients"
    ),
    "cafe": (
        "spilled drink, melted cream, broken glass, unnatural foam, "
        "dirty cup, collapsed dessert"
    ),
    "beauty": (
        "distorted face, unrealistic skin texture, extra eyes, damaged hair, "
        "harsh shadows, medical injury"
    ),
    "fitness": (
        "distorted body, extra limbs, unsafe exercise posture, broken equipment, "
        "unrealistic muscles, injury"
    ),
    "retail": (
        "distorted product, broken package, fake brand label, unreadable label, "
        "duplicate product, warped edges"
    ),
}

BUSINESS_TYPE_ALIASES: dict[str, str] = {
    "food": "restaurant",
    "restaurant": "restaurant",
    "cafe": "cafe",
    "beverage": "cafe",
    "beauty": "beauty",
    "salon": "beauty",
    "fitness": "fitness",
    "gym": "fitness",
    "retail": "retail",
    "product": "retail",
}


def resolve_negative_prompt(user_negative_prompt: str | None, metadata: dict[str, Any] | None) -> str:
    """Merge common, industry, and user negative prompts without duplicates."""
    metadata = metadata or {}
    sources = [COMMON_NEGATIVE_PROMPT]
    industry = resolve_industry_key(metadata.get("business_type"))
    if industry and industry in INDUSTRY_NEGATIVE_PROMPTS:
        sources.append(INDUSTRY_NEGATIVE_PROMPTS[industry])
    if user_negative_prompt:
        sources.append(user_negative_prompt)
    return ", ".join(_dedupe_phrases(sources))


def resolve_negative_prompt_sources(user_negative_prompt: str | None, metadata: dict[str, Any] | None) -> list[str]:
    """Return source labels used to build the effective negative prompt."""
    metadata = metadata or {}
    sources = ["common"]
    industry = resolve_industry_key(metadata.get("business_type"))
    if industry and industry in INDUSTRY_NEGATIVE_PROMPTS:
        sources.append(f"industry:{industry}")
    if user_negative_prompt:
        sources.append("user")
    return sources


def resolve_industry_key(raw_business_type: object) -> str | None:
    """Normalize metadata.business_type to a supported industry key."""
    if raw_business_type is None:
        return None
    value = str(raw_business_type).strip().lower()
    return BUSINESS_TYPE_ALIASES.get(value, value if value in INDUSTRY_NEGATIVE_PROMPTS else None)


def _dedupe_phrases(prompt_sources: list[str]) -> list[str]:
    seen: set[str] = set()
    phrases: list[str] = []
    for source in prompt_sources:
        for phrase in source.split(","):
            clean = " ".join(phrase.strip().split())
            key = clean.lower()
            if clean and key not in seen:
                phrases.append(clean)
                seen.add(key)
    return phrases