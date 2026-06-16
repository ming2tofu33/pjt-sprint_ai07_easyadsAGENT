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

from enum import StrEnum
from typing import Literal, NamedTuple

from pydantic import BaseModel, Field, model_validator


# Track A-1 v1 contract types. These pure declarations unblock Track B while
# existing Phase 1 compatibility helpers remain unchanged until A-2 rewiring.
class CanonicalBusinessDomain(StrEnum):
    FOOD_AND_BEVERAGE = "food_and_beverage"
    BEAUTY = "beauty"
    RETAIL = "retail"
    OTHER = "other"


class DomainSupportStatus(StrEnum):
    SPECIALIZED = "specialized"
    GENERIC_FALLBACK = "generic_fallback"
    NEEDS_EVIDENCE = "needs_evidence"
    UNRESOLVED = "unresolved"


class DomainFallbackReason(StrEnum):
    UNSUPPORTED_DOMAIN_IN_MVP = "unsupported_domain_in_mvp"
    AMBIGUOUS_BEAUTY_SUBDOMAIN = "ambiguous_beauty_subdomain"
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"
    NO_SPECIALIZED_VISUAL_PROFILE = "no_specialized_visual_profile"
    UNRECOGNIZED_BUSINESS_TYPE = "unrecognized_business_type"


class RoutingEvidenceSource(StrEnum):
    USER_TEXT = "user_text"
    IMAGE_VLM = "image_vlm"
    BRIEF_LLM = "brief_llm"
    ASSET_METADATA = "asset_metadata"
    BRAND_PROFILE = "brand_profile"
    REFERENCE_METADATA = "reference_metadata"
    LEGACY_ALIAS = "legacy_alias"


class RoutingTagEvidence(BaseModel):
    tag: str = Field(min_length=1, pattern=r"^[a-z0-9][a-z0-9_-]*$")
    source: RoutingEvidenceSource
    confidence: float = Field(ge=0.0, le=1.0)
    usable_for_routing: bool = True
    evidence_ref: str | None = None


class DomainRoutingResult(BaseModel):
    contract_version: Literal["1.0"] = "1.0"
    raw_business_type: str | None
    canonical_domain: CanonicalBusinessDomain
    support_status: DomainSupportStatus
    unsupported_domain_hint: str | None = None
    business_tags: list[RoutingTagEvidence] = Field(default_factory=list)
    scene_tags: list[RoutingTagEvidence] = Field(default_factory=list)
    style_tags: list[RoutingTagEvidence] = Field(default_factory=list)
    fallback_reason: DomainFallbackReason | None = None
    matched_aliases: list[str] = Field(default_factory=list)
    evidence_refs: list[str] = Field(default_factory=list)
    clarification_required: bool = False
    unresolved_questions: list[str] = Field(default_factory=list)
    confidence: float = Field(ge=0.0, le=1.0)

    @model_validator(mode="after")
    def validate_status_contract(self) -> "DomainRoutingResult":
        if self.support_status == DomainSupportStatus.SPECIALIZED and self.fallback_reason is not None:
            raise ValueError("specialized routing must not include fallback_reason")
        if (
            self.support_status
            in {
                DomainSupportStatus.GENERIC_FALLBACK,
                DomainSupportStatus.NEEDS_EVIDENCE,
                DomainSupportStatus.UNRESOLVED,
            }
            and self.fallback_reason is None
        ):
            raise ValueError("non-specialized routing requires fallback_reason")
        if (
            self.support_status
            in {
                DomainSupportStatus.NEEDS_EVIDENCE,
                DomainSupportStatus.UNRESOLVED,
            }
            and not self.clarification_required
        ):
            raise ValueError("needs_evidence/unresolved must require clarification")
        if self.canonical_domain != CanonicalBusinessDomain.OTHER and self.unsupported_domain_hint is not None:
            raise ValueError("unsupported_domain_hint is only valid for OTHER")
        return self


class LegacyVisualRouteKey(StrEnum):
    CAFE = "cafe"
    RESTAURANT = "restaurant"
    RESTAURANT_BBQ = "restaurant_bbq"
    BEAUTY_SKINCARE = "beauty_skincare"
    BEAUTY_HAIR = "beauty_hair"
    BEAUTY_NAIL = "beauty_nail"
    BEAUTY_SPA = "beauty_spa"
    GENERIC = "generic"


class LegacyRoutingProjection(BaseModel):
    projection_version: Literal["1.0"] = "1.0"
    route_key: LegacyVisualRouteKey
    reason_codes: list[str] = Field(default_factory=list)
    evidence_refs: list[str] = Field(default_factory=list)
    fallback_used: bool = False
    fallback_reason: DomainFallbackReason | None = None
    deprecated: Literal[True] = True


class ReferenceTemplateRoutingProfile(BaseModel):
    contract_version: Literal["1.0"] = "1.0"
    applies_to_all_domains: bool = False
    business_domains: set[CanonicalBusinessDomain] = Field(default_factory=set)
    business_tags: set[str] = Field(default_factory=set)
    product_tags: set[str] = Field(default_factory=set)
    scene_tags: set[str] = Field(default_factory=set)
    style_tags: set[str] = Field(default_factory=set)
    placements: set[str] = Field(default_factory=set)
    excluded_tags: set[str] = Field(default_factory=set)

    @model_validator(mode="after")
    def validate_routing_profile(self) -> "ReferenceTemplateRoutingProfile":
        if (
            not self.applies_to_all_domains
            and not self.business_domains
            and not self.business_tags
            and not self.product_tags
            and not self.scene_tags
            and not self.style_tags
        ):
            raise ValueError("routing profile requires at least one routing dimension")
        included_tags = self.business_tags | self.product_tags | self.scene_tags | self.style_tags
        if included_tags & self.excluded_tags:
            raise ValueError("included and excluded tags must not overlap")
        return self

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
