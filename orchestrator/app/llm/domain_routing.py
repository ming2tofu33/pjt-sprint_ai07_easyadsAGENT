"""Single source of truth (SSOT) for business-type domain routing.

Today the "업종" concept is hardcoded across 6+ vocabularies that drift apart
(see docs/PRESET_ROUTING_AUDIT.md, docs/2026-06-16-domain-routing-ssot-roadmap.md).
This module owns the Track A canonical routing contract. The current A-2 layer
normalises raw/brief values into the A-1 DomainRoutingResult model while keeping
temporary compatibility properties for legacy callers.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Literal

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

    @property
    def canonical(self) -> str:
        """Legacy compatibility: old callers read a string `.canonical` value."""
        return self.canonical_domain.value

    @property
    def supported(self) -> bool:
        """Legacy compatibility: only fully specialized results are supported."""
        return self.support_status == DomainSupportStatus.SPECIALIZED

    @property
    def legacy_fallback_reason(self) -> str | None:
        """String fallback reason for callers that cannot consume StrEnum yet."""
        return self.fallback_reason.value if self.fallback_reason else None

    @property
    def business_type(self) -> str | None:
        """Legacy context.business_type projection until A-5 single-key wiring.

        This is intentionally a property, not a Pydantic field: the canonical
        contract is domain + tags + evidence, while this value only keeps today's
        downstream selectors alive during the transition.
        """
        tags = _tag_set(self.business_tags)
        if self.support_status == DomainSupportStatus.UNRESOLVED:
            return None
        if self.canonical_domain == CanonicalBusinessDomain.FOOD_AND_BEVERAGE:
            if "restaurant" in tags:
                return "restaurant"
            if "cafe" in tags:
                return "cafe"
            return None
        if self.canonical_domain == CanonicalBusinessDomain.BEAUTY:
            if "hair" in tags:
                return "beauty_hair"
            if "nail" in tags:
                return "beauty_nail"
            if "spa" in tags:
                return "beauty_spa"
            if "skincare" in tags:
                return "beauty_skincare"
            return None
        if self.canonical_domain == CanonicalBusinessDomain.RETAIL:
            return "retail"
        if self.canonical_domain == CanonicalBusinessDomain.OTHER:
            return self.unsupported_domain_hint
        return None


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

# Canonical business domains are intentionally coarse. Legacy route keys such as
# cafe, restaurant_bbq, and beauty_hair are tags/projections, not canonical values.
CanonicalDomain = Literal[
    "food_and_beverage",
    "beauty",
    "retail",
    "other",
]

CANONICAL_DOMAINS: frozenset[str] = frozenset(item.value for item in CanonicalBusinessDomain)

SUPPORTED_DOMAINS: frozenset[str] = frozenset(
    {
        CanonicalBusinessDomain.FOOD_AND_BEVERAGE.value,
        CanonicalBusinessDomain.BEAUTY.value,
        CanonicalBusinessDomain.RETAIL.value,
    }
)

_DOMAIN_ALIASES: dict[str, CanonicalBusinessDomain] = {
    "food_and_beverage": CanonicalBusinessDomain.FOOD_AND_BEVERAGE,
    "cafe": CanonicalBusinessDomain.FOOD_AND_BEVERAGE,
    "dessert": CanonicalBusinessDomain.FOOD_AND_BEVERAGE,
    "bakery": CanonicalBusinessDomain.FOOD_AND_BEVERAGE,
    "macaron": CanonicalBusinessDomain.FOOD_AND_BEVERAGE,
    "restaurant": CanonicalBusinessDomain.FOOD_AND_BEVERAGE,
    "restaurant_bbq": CanonicalBusinessDomain.FOOD_AND_BEVERAGE,
    "bbq": CanonicalBusinessDomain.FOOD_AND_BEVERAGE,
    "korean_food": CanonicalBusinessDomain.FOOD_AND_BEVERAGE,
    "meat_restaurant": CanonicalBusinessDomain.FOOD_AND_BEVERAGE,
    "dining": CanonicalBusinessDomain.FOOD_AND_BEVERAGE,
    "food": CanonicalBusinessDomain.FOOD_AND_BEVERAGE,
    "beauty": CanonicalBusinessDomain.BEAUTY,
    "beauty_salon": CanonicalBusinessDomain.BEAUTY,
    "beauty_skincare": CanonicalBusinessDomain.BEAUTY,
    "beauty_hair": CanonicalBusinessDomain.BEAUTY,
    "beauty_nail": CanonicalBusinessDomain.BEAUTY,
    "beauty_spa": CanonicalBusinessDomain.BEAUTY,
    "salon": CanonicalBusinessDomain.BEAUTY,
    "skincare": CanonicalBusinessDomain.BEAUTY,
    "hair_salon": CanonicalBusinessDomain.BEAUTY,
    "nail": CanonicalBusinessDomain.BEAUTY,
    "spa": CanonicalBusinessDomain.BEAUTY,
    "retail": CanonicalBusinessDomain.RETAIL,
    "store": CanonicalBusinessDomain.RETAIL,
    "ecommerce": CanonicalBusinessDomain.RETAIL,
    "flower_shop": CanonicalBusinessDomain.RETAIL,
    "bar": CanonicalBusinessDomain.OTHER,
    "fitness": CanonicalBusinessDomain.OTHER,
    "academy": CanonicalBusinessDomain.OTHER,
    "education": CanonicalBusinessDomain.OTHER,
    "service": CanonicalBusinessDomain.OTHER,
    "professional_service": CanonicalBusinessDomain.OTHER,
    "local_service": CanonicalBusinessDomain.OTHER,
    "home_service": CanonicalBusinessDomain.OTHER,
    "other": CanonicalBusinessDomain.OTHER,
}

_BUSINESS_TAGS_BY_ALIAS: dict[str, tuple[str, ...]] = {
    "food_and_beverage": (),
    "cafe": ("cafe",),
    "dessert": ("cafe", "dessert_shop"),
    "bakery": ("bakery",),
    "macaron": ("cafe", "dessert_shop"),
    "restaurant": ("restaurant",),
    "restaurant_bbq": ("restaurant", "korean_bbq"),
    "bbq": ("restaurant", "korean_bbq"),
    "korean_food": ("restaurant", "korean_food"),
    "meat_restaurant": ("restaurant", "korean_bbq"),
    "dining": ("restaurant",),
    "food": ("restaurant",),
    "beauty": ("beauty_service",),
    "beauty_salon": ("beauty_service",),
    "salon": ("beauty_service",),
    "beauty_skincare": ("skincare",),
    "beauty_hair": ("hair",),
    "beauty_nail": ("nail",),
    "beauty_spa": ("spa",),
    "skincare": ("skincare",),
    "hair_salon": ("hair",),
    "nail": ("nail",),
    "spa": ("spa",),
    "retail": ("retail",),
    "store": ("retail", "physical_store"),
    "ecommerce": ("retail", "ecommerce"),
    "flower_shop": ("retail", "flower_shop"),
    "bar": ("bar",),
    "fitness": ("fitness",),
    "academy": ("education", "academy"),
    "education": ("education",),
    "service": ("service",),
    "professional_service": ("professional_service",),
    "local_service": ("local_service",),
    "home_service": ("home_service",),
    "other": ("other",),
}

_AMBIGUOUS_BEAUTY_ALIASES = frozenset({"beauty", "beauty_salon", "salon"})
_UNSUPPORTED_DOMAIN_HINTS: dict[str, str] = {
    "bar": "bar",
    "fitness": "fitness",
    "academy": "education",
    "education": "education",
    "service": "service",
    "professional_service": "professional_service",
    "local_service": "local_service",
    "home_service": "home_service",
    "other": "other",
}
_SCENE_EVIDENCE_TAGS = frozenset({"bbq_grill", "charcoal_grill"})
_SOURCE_ALIAS_SPANS: dict[str, str] = {
    "뷰티샵": "beauty",
    "뷰티": "beauty",
    "미용실": "beauty_salon",
    "살롱": "salon",
    "네일샵": "beauty_nail",
    "네일": "nail",
    "스파": "spa",
    "카페": "cafe",
    "베이커리": "bakery",
    "레스토랑": "restaurant",
    "음식점": "restaurant",
    "식당": "restaurant",
    "고깃집": "restaurant_bbq",
    "매장": "store",
    "상점": "store",
    "소품샵": "store",
    "꽃집": "flower_shop",
}


def _normalized_key(value: str | CanonicalBusinessDomain | None) -> str:
    if isinstance(value, CanonicalBusinessDomain):
        return value.value
    return str(value or "").strip().lower()


def find_business_alias_span(text: str | None) -> tuple[str | None, str | None]:
    source = str(text or "").strip()
    if not source:
        return None, None
    for phrase in sorted(_SOURCE_ALIAS_SPANS, key=len, reverse=True):
        if phrase in source:
            return phrase, _SOURCE_ALIAS_SPANS[phrase]
    lowered = source.lower()
    for alias in sorted(_DOMAIN_ALIASES, key=len, reverse=True):
        if not alias or "_" in alias:
            continue
        if alias in lowered:
            return alias, alias
    return None, None


def _tag(
    tag: str,
    *,
    source: RoutingEvidenceSource = RoutingEvidenceSource.LEGACY_ALIAS,
    confidence: float = 1.0,
    evidence_ref: str | None = None,
) -> RoutingTagEvidence:
    return RoutingTagEvidence(
        tag=tag,
        source=source,
        confidence=confidence,
        evidence_ref=evidence_ref,
    )


def _tag_set(tags: list[RoutingTagEvidence]) -> set[str]:
    return {tag.tag for tag in tags}


def _scene_tags_from_evidence(evidence: list[RoutingTagEvidence] | None) -> list[RoutingTagEvidence]:
    if not evidence:
        return []
    return [
        tag
        for tag in evidence
        if tag.usable_for_routing and tag.tag in _SCENE_EVIDENCE_TAGS
    ]


_BBQ_PRODUCT_EVIDENCE_TAGS = frozenset({"grilled_meat"})
_BBQ_SCENE_EVIDENCE_TAGS = frozenset({"bbq_grill", "charcoal_grill", "table_grill"})


def _normalized_tag_set(values: set[str] | list[str] | tuple[str, ...] | None) -> set[str]:
    return {
        str(value).strip().lower()
        for value in values or ()
        if str(value).strip()
    }


def _usable_tag_set(tags: list[RoutingTagEvidence]) -> set[str]:
    return {tag.tag for tag in tags if tag.usable_for_routing}


def _generic_projection(
    *,
    reason: DomainFallbackReason,
    evidence_refs: list[str],
) -> LegacyRoutingProjection:
    return LegacyRoutingProjection(
        route_key=LegacyVisualRouteKey.GENERIC,
        reason_codes=[reason.value],
        evidence_refs=evidence_refs,
        fallback_used=True,
        fallback_reason=reason,
    )


def project_to_legacy_visual_route(
    domain_result: DomainRoutingResult,
    *,
    product_tags: set[str],
    explicit_scene_tags: set[str],
) -> LegacyRoutingProjection:
    """Project canonical routing into the deprecated visual route key space.

    This adapter is the only place where legacy visual keys such as
    `restaurant_bbq` should be created during the transition period.
    """
    business_tags = _usable_tag_set(domain_result.business_tags)
    scene_tags = _usable_tag_set(domain_result.scene_tags) | _normalized_tag_set(explicit_scene_tags)
    product_tag_set = _normalized_tag_set(product_tags)
    evidence_refs = list(domain_result.evidence_refs)

    if domain_result.canonical_domain == CanonicalBusinessDomain.FOOD_AND_BEVERAGE:
        if "cafe" in business_tags:
            return LegacyRoutingProjection(
                route_key=LegacyVisualRouteKey.CAFE,
                reason_codes=["cafe_business_tag"],
                evidence_refs=evidence_refs,
            )
        if "restaurant" in business_tags:
            has_bbq_visual_evidence = bool(
                ("korean_bbq" in business_tags)
                and (
                    product_tag_set & _BBQ_PRODUCT_EVIDENCE_TAGS
                    or scene_tags & _BBQ_SCENE_EVIDENCE_TAGS
                )
            )
            if has_bbq_visual_evidence:
                return LegacyRoutingProjection(
                    route_key=LegacyVisualRouteKey.RESTAURANT_BBQ,
                    reason_codes=["bbq_visual_evidence"],
                    evidence_refs=evidence_refs,
                )
            reason_codes = ["restaurant_business_tag"]
            if "korean_bbq" in business_tags:
                reason_codes.append("korean_bbq_without_visual_evidence")
            return LegacyRoutingProjection(
                route_key=LegacyVisualRouteKey.RESTAURANT,
                reason_codes=reason_codes,
                evidence_refs=evidence_refs,
            )
        return _generic_projection(
            reason=DomainFallbackReason.NO_SPECIALIZED_VISUAL_PROFILE,
            evidence_refs=evidence_refs,
        )

    if domain_result.canonical_domain == CanonicalBusinessDomain.BEAUTY:
        if "skincare" in business_tags:
            return LegacyRoutingProjection(
                route_key=LegacyVisualRouteKey.BEAUTY_SKINCARE,
                reason_codes=["beauty_subtype_evidence"],
                evidence_refs=evidence_refs,
            )
        if "hair" in business_tags:
            return LegacyRoutingProjection(
                route_key=LegacyVisualRouteKey.BEAUTY_HAIR,
                reason_codes=["beauty_subtype_evidence"],
                evidence_refs=evidence_refs,
            )
        if "nail" in business_tags:
            return LegacyRoutingProjection(
                route_key=LegacyVisualRouteKey.BEAUTY_NAIL,
                reason_codes=["beauty_subtype_evidence"],
                evidence_refs=evidence_refs,
            )
        if "spa" in business_tags:
            return LegacyRoutingProjection(
                route_key=LegacyVisualRouteKey.BEAUTY_SPA,
                reason_codes=["beauty_subtype_evidence"],
                evidence_refs=evidence_refs,
            )
        return _generic_projection(
            reason=domain_result.fallback_reason or DomainFallbackReason.AMBIGUOUS_BEAUTY_SUBDOMAIN,
            evidence_refs=evidence_refs,
        )

    if domain_result.canonical_domain == CanonicalBusinessDomain.RETAIL:
        return _generic_projection(
            reason=DomainFallbackReason.NO_SPECIALIZED_VISUAL_PROFILE,
            evidence_refs=evidence_refs,
        )

    return _generic_projection(
        reason=domain_result.fallback_reason or DomainFallbackReason.UNRECOGNIZED_BUSINESS_TYPE,
        evidence_refs=evidence_refs,
    )


def to_canonical_domain(value: str | CanonicalBusinessDomain | None) -> CanonicalBusinessDomain:
    """Classify a raw/brief/subtype value to the A-1 canonical domain.

    This is exact alias lookup only. Unknown or empty values are intentionally
    classified as OTHER here; `normalize_business_type()` records whether that
    OTHER result is an explicit unsupported domain or an unresolved unknown.
    """
    return _DOMAIN_ALIASES.get(_normalized_key(value), CanonicalBusinessDomain.OTHER)


def is_supported_domain(value: str | CanonicalBusinessDomain | None) -> bool:
    """True when the canonical domain is in the MVP specialized set."""
    return to_canonical_domain(value) in {
        CanonicalBusinessDomain.FOOD_AND_BEVERAGE,
        CanonicalBusinessDomain.BEAUTY,
        CanonicalBusinessDomain.RETAIL,
    }


def normalize_business_type(
    raw_business_type: str | CanonicalBusinessDomain | None,
    *,
    evidence: list[RoutingTagEvidence] | None = None,
) -> DomainRoutingResult:
    """Normalise an input-boundary business value into DomainRoutingResult."""
    key = _normalized_key(raw_business_type)
    raw = None if raw_business_type is None else str(raw_business_type).strip()
    domain = _DOMAIN_ALIASES.get(key)
    evidence_refs = [
        tag.evidence_ref
        for tag in evidence or []
        if tag.usable_for_routing and tag.evidence_ref
    ]

    if not key or domain is None:
        return DomainRoutingResult(
            raw_business_type=raw,
            canonical_domain=CanonicalBusinessDomain.OTHER,
            support_status=DomainSupportStatus.UNRESOLVED,
            fallback_reason=DomainFallbackReason.UNRECOGNIZED_BUSINESS_TYPE,
            clarification_required=True,
            unresolved_questions=["Provide a clearer business category."],
            evidence_refs=evidence_refs,
            confidence=0.0,
        )

    business_tags = [
        _tag(tag, evidence_ref=f"business_type:{key}")
        for tag in _BUSINESS_TAGS_BY_ALIAS.get(key, ())
    ]
    scene_tags = _scene_tags_from_evidence(evidence)

    if key in _UNSUPPORTED_DOMAIN_HINTS:
        return DomainRoutingResult(
            raw_business_type=raw,
            canonical_domain=CanonicalBusinessDomain.OTHER,
            support_status=DomainSupportStatus.GENERIC_FALLBACK,
            unsupported_domain_hint=_UNSUPPORTED_DOMAIN_HINTS[key],
            business_tags=business_tags,
            scene_tags=scene_tags,
            fallback_reason=DomainFallbackReason.UNSUPPORTED_DOMAIN_IN_MVP,
            matched_aliases=[key],
            evidence_refs=evidence_refs,
            confidence=0.85,
        )

    if domain == CanonicalBusinessDomain.BEAUTY and key in _AMBIGUOUS_BEAUTY_ALIASES:
        return DomainRoutingResult(
            raw_business_type=raw,
            canonical_domain=domain,
            support_status=DomainSupportStatus.NEEDS_EVIDENCE,
            business_tags=business_tags,
            scene_tags=scene_tags,
            fallback_reason=DomainFallbackReason.AMBIGUOUS_BEAUTY_SUBDOMAIN,
            matched_aliases=[key],
            evidence_refs=evidence_refs,
            clarification_required=True,
            unresolved_questions=["Choose a beauty subtype: skincare, hair, nail, or spa."],
            confidence=0.72,
        )

    return DomainRoutingResult(
        raw_business_type=raw,
        canonical_domain=domain,
        support_status=DomainSupportStatus.SPECIALIZED,
        business_tags=business_tags,
        scene_tags=scene_tags,
        matched_aliases=[key],
        evidence_refs=evidence_refs,
        confidence=0.95,
    )
