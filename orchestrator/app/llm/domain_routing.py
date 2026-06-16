"""Single source of truth (SSOT) for business-type domain routing.

Today the "업종" concept is hardcoded across 6+ vocabularies that drift apart
(see docs/PRESET_ROUTING_AUDIT.md, docs/2026-06-16-domain-routing-ssot-roadmap.md).
This module is the Phase 1 foundation: it declares the canonical domains in ONE
place and normalises raw/brief values into them.

Phase 1 is intentionally small and behaviour-preserving for downstream selection.
It does NOT rewire scene_planner / templates / presets onto a shared resolved key
(that is Phase 2), nor introduce a business_type-vs-scene axis (Phase 3). It only
gives the input boundary (brief_interpreter) a single declared mapping and makes
unsupported-domain fallbacks observable instead of silent.
"""

from __future__ import annotations

from typing import Literal, NamedTuple

# Coarse canonical business domains. All seven are declared so the full taxonomy
# is visible in one place even though some do not have a visual/copy strategy yet.
CanonicalDomain = Literal[
    "cafe",
    "restaurant",
    "beauty",
    "fitness",
    "retail",
    "education",
    "service",
]

CANONICAL_DOMAINS: frozenset[str] = frozenset(
    {"cafe", "restaurant", "beauty", "fitness", "retail", "education", "service"}
)

# Domains that are actually backed by a preset/template/copy strategy today.
# The remaining declared domains (fitness/retail/education/service) intentionally
# delegate to the generic strategy until Phase 4 fills them in.
SUPPORTED_DOMAINS: frozenset[str] = frozenset({"cafe", "restaurant", "beauty"})

# Raw input strings / subtypes / scene-mixed values / Korean keywords -> canonical
# coarse domain. Exact-match alias layer only (no heavy substring heuristics in
# Phase 1 — those stay in scene_planner). Keys are matched case-insensitively.
_ALIASES: dict[str, str] = {
    # cafe
    "dessert": "cafe",
    "bakery": "cafe",
    "macaron": "cafe",
    # restaurant (incl. the bbq scene value we keep as-is for now)
    "restaurant_bbq": "restaurant",
    "bbq": "restaurant",
    "korean_food": "restaurant",
    "meat_restaurant": "restaurant",
    "dining": "restaurant",
    "food": "restaurant",
    # beauty (subtype + scene-mixed values all collapse to the beauty family)
    "beauty_salon": "beauty",
    "beauty_skincare": "beauty",
    "beauty_hair": "beauty",
    "beauty_nail": "beauty",
    "beauty_spa": "beauty",
    "salon": "beauty",
    "skincare": "beauty",
    "hair_salon": "beauty",
    "nail": "beauty",
    "spa": "beauty",
}

# Canonical domain -> the context.business_type value that downstream selectors
# expect TODAY. This deliberately reproduces current behaviour:
#   - beauty resolves to the ambiguous "beauty_salon" (which scene_planner/preset
#     then narrow to skincare),
#   - fitness keeps mapping to "fitness" (no strategy -> generic downstream),
#   - retail/education/service have no context value yet (None -> generic).
_CANONICAL_TO_CONTEXT_BUSINESS_TYPE: dict[str, str | None] = {
    "cafe": "cafe",
    "restaurant": "restaurant",
    "beauty": "beauty_salon",
    "fitness": "fitness",
    "retail": None,
    "education": None,
    "service": None,
}


class NormalizedBusinessType(NamedTuple):
    """Result of normalising a raw/brief business value at the input boundary."""

    canonical: str | None
    business_type: str | None
    supported: bool
    fallback_reason: str | None


def to_canonical_domain(value: str | None) -> str | None:
    """Classify any raw/brief/subtype value to a coarse canonical domain.

    Returns one of CANONICAL_DOMAINS, or None when the value is unknown/empty.
    Exact match first, then the alias layer. No substring heuristics (Phase 1).
    """
    if not value:
        return None
    key = value.strip().lower()
    if key in CANONICAL_DOMAINS:
        return key
    return _ALIASES.get(key)


def is_supported_domain(value: str | None) -> bool:
    """True when the value maps to a domain that has a real strategy today."""
    canonical = to_canonical_domain(value)
    return canonical in SUPPORTED_DOMAINS


def normalize_business_type(value: str | None) -> NormalizedBusinessType:
    """Normalise an input-boundary business value into the SSOT shape.

    `business_type` is the value to feed downstream selectors and reproduces
    today's behaviour exactly. `fallback_reason` is non-None whenever the result
    falls back to the generic strategy (unknown value, or a declared-but-not-yet
    -supported domain) so the fallback is observable rather than silent.
    """
    canonical = to_canonical_domain(value)

    if canonical is None:
        raw = (value or "").strip()
        reason = (
            f"unknown_business_type: {raw}" if raw else "missing_business_type"
        )
        return NormalizedBusinessType(
            canonical=None, business_type=None, supported=False, fallback_reason=reason
        )

    business_type = _CANONICAL_TO_CONTEXT_BUSINESS_TYPE[canonical]
    supported = canonical in SUPPORTED_DOMAINS
    fallback_reason = (
        None if supported else f"{canonical} has no domain routing yet"
    )
    return NormalizedBusinessType(
        canonical=canonical,
        business_type=business_type,
        supported=supported,
        fallback_reason=fallback_reason,
    )
