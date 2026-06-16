"""Unit tests for the domain-routing SSOT.

A-2 pins the new normalization semantics from docs/two track.md:
canonical domains are 3+1, legacy preset/template keys are no longer canonical,
and ambiguous/unsupported domains must produce explicit routing metadata.
"""

from __future__ import annotations

from typing import get_args

import pytest

from orchestrator.app.llm.domain_routing import (
    CANONICAL_DOMAINS,
    SUPPORTED_DOMAINS,
    CanonicalBusinessDomain,
    CanonicalDomain,
    DomainFallbackReason,
    DomainSupportStatus,
    LegacyVisualRouteKey,
    RoutingEvidenceSource,
    RoutingTagEvidence,
    is_supported_domain,
    normalize_business_type,
    project_to_legacy_visual_route,
    to_canonical_domain,
)


def _tags(result) -> set[str]:
    return {tag.tag for tag in result.business_tags}


def _scene_tags(result) -> set[str]:
    return {tag.tag for tag in result.scene_tags}


def test_canonical_literal_matches_declared_set():
    assert set(get_args(CanonicalDomain)) == set(CANONICAL_DOMAINS)


def test_canonical_domains_are_mvp_3_plus_other():
    assert CANONICAL_DOMAINS == {
        "food_and_beverage",
        "beauty",
        "retail",
        "other",
    }


def test_supported_domains_are_mvp_specialized_domains():
    assert SUPPORTED_DOMAINS <= CANONICAL_DOMAINS
    assert SUPPORTED_DOMAINS == {
        "food_and_beverage",
        "beauty",
        "retail",
    }


# --- to_canonical_domain: exact aliases only, no substring matching ----------

@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("food_and_beverage", CanonicalBusinessDomain.FOOD_AND_BEVERAGE),
        ("cafe", CanonicalBusinessDomain.FOOD_AND_BEVERAGE),
        ("Cafe", CanonicalBusinessDomain.FOOD_AND_BEVERAGE),
        ("  CAFE  ", CanonicalBusinessDomain.FOOD_AND_BEVERAGE),
        ("dessert", CanonicalBusinessDomain.FOOD_AND_BEVERAGE),
        ("bakery", CanonicalBusinessDomain.FOOD_AND_BEVERAGE),
        ("restaurant", CanonicalBusinessDomain.FOOD_AND_BEVERAGE),
        ("restaurant_bbq", CanonicalBusinessDomain.FOOD_AND_BEVERAGE),
        ("bbq", CanonicalBusinessDomain.FOOD_AND_BEVERAGE),
        ("korean_food", CanonicalBusinessDomain.FOOD_AND_BEVERAGE),
        ("meat_restaurant", CanonicalBusinessDomain.FOOD_AND_BEVERAGE),
        ("beauty", CanonicalBusinessDomain.BEAUTY),
        ("beauty_salon", CanonicalBusinessDomain.BEAUTY),
        ("beauty_skincare", CanonicalBusinessDomain.BEAUTY),
        ("beauty_hair", CanonicalBusinessDomain.BEAUTY),
        ("beauty_nail", CanonicalBusinessDomain.BEAUTY),
        ("beauty_spa", CanonicalBusinessDomain.BEAUTY),
        ("retail", CanonicalBusinessDomain.RETAIL),
        ("fitness", CanonicalBusinessDomain.OTHER),
        ("education", CanonicalBusinessDomain.OTHER),
        ("service", CanonicalBusinessDomain.OTHER),
        ("professional_service", CanonicalBusinessDomain.OTHER),
        ("local_service", CanonicalBusinessDomain.OTHER),
        ("home_service", CanonicalBusinessDomain.OTHER),
        ("other", CanonicalBusinessDomain.OTHER),
    ],
)
def test_to_canonical_domain_returns_a1_domain(value, expected):
    assert to_canonical_domain(value) == expected


@pytest.mark.parametrize("value", [None, "", "   ", "spaceship", "generic"])
def test_to_canonical_domain_unknown_values_are_other(value):
    assert to_canonical_domain(value) == CanonicalBusinessDomain.OTHER


def test_no_substring_matching_in_a2():
    assert to_canonical_domain("korean cafe restaurant") == CanonicalBusinessDomain.OTHER


# --- normalize_business_type: DomainRoutingResult contract ------------------

def test_normalize_cafe_routes_to_food_and_beverage_cafe_tag():
    result = normalize_business_type("cafe")

    assert result.canonical_domain == CanonicalBusinessDomain.FOOD_AND_BEVERAGE
    assert result.support_status == DomainSupportStatus.SPECIALIZED
    assert _tags(result) == {"cafe"}
    assert result.fallback_reason is None


def test_normalize_restaurant_bbq_keeps_scene_unset_without_evidence():
    result = normalize_business_type("restaurant_bbq")

    assert result.canonical_domain == CanonicalBusinessDomain.FOOD_AND_BEVERAGE
    assert result.support_status == DomainSupportStatus.SPECIALIZED
    assert {"restaurant", "korean_bbq"} <= _tags(result)
    assert "bbq_grill" not in _scene_tags(result)
    assert result.fallback_reason is None


def test_normalize_restaurant_bbq_can_accept_explicit_scene_evidence():
    result = normalize_business_type(
        "restaurant_bbq",
        evidence=[
            RoutingTagEvidence(
                tag="bbq_grill",
                source=RoutingEvidenceSource.USER_TEXT,
                confidence=0.9,
            )
        ],
    )

    assert "bbq_grill" in _scene_tags(result)


def test_project_restaurant_bbq_requires_product_or_scene_evidence():
    result = normalize_business_type("restaurant_bbq")

    projection = project_to_legacy_visual_route(
        result,
        product_tags=set(),
        explicit_scene_tags=set(),
    )

    assert projection.route_key == LegacyVisualRouteKey.RESTAURANT
    assert projection.fallback_used is False
    assert projection.fallback_reason is None
    assert "korean_bbq_without_visual_evidence" in projection.reason_codes


def test_project_restaurant_bbq_allows_grilled_meat_product_evidence():
    result = normalize_business_type("restaurant_bbq")

    projection = project_to_legacy_visual_route(
        result,
        product_tags={"grilled_meat"},
        explicit_scene_tags=set(),
    )

    assert projection.route_key == LegacyVisualRouteKey.RESTAURANT_BBQ
    assert projection.fallback_used is False
    assert "bbq_visual_evidence" in projection.reason_codes


def test_project_restaurant_bbq_allows_explicit_bbq_scene_evidence():
    result = normalize_business_type("restaurant_bbq")

    projection = project_to_legacy_visual_route(
        result,
        product_tags=set(),
        explicit_scene_tags={"bbq_grill"},
    )

    assert projection.route_key == LegacyVisualRouteKey.RESTAURANT_BBQ
    assert projection.fallback_used is False
    assert "bbq_visual_evidence" in projection.reason_codes


def test_normalize_beauty_salon_requires_evidence():
    result = normalize_business_type("beauty_salon")

    assert result.canonical_domain == CanonicalBusinessDomain.BEAUTY
    assert result.support_status == DomainSupportStatus.NEEDS_EVIDENCE
    assert result.fallback_reason == DomainFallbackReason.AMBIGUOUS_BEAUTY_SUBDOMAIN
    assert result.clarification_required is True
    assert result.business_type is None


@pytest.mark.parametrize(
    ("value", "business_type"),
    [
        ("beauty_skincare", "beauty_skincare"),
        ("beauty_hair", "beauty_hair"),
        ("beauty_nail", "beauty_nail"),
        ("beauty_spa", "beauty_spa"),
    ],
)
def test_normalize_explicit_beauty_subtypes_are_specialized(value, business_type):
    result = normalize_business_type(value)

    assert result.canonical_domain == CanonicalBusinessDomain.BEAUTY
    assert result.support_status == DomainSupportStatus.SPECIALIZED
    assert result.business_type == business_type
    assert result.fallback_reason is None


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("beauty_skincare", LegacyVisualRouteKey.BEAUTY_SKINCARE),
        ("beauty_hair", LegacyVisualRouteKey.BEAUTY_HAIR),
        ("beauty_nail", LegacyVisualRouteKey.BEAUTY_NAIL),
        ("beauty_spa", LegacyVisualRouteKey.BEAUTY_SPA),
    ],
)
def test_project_explicit_beauty_subtypes(value, expected):
    projection = project_to_legacy_visual_route(
        normalize_business_type(value),
        product_tags=set(),
        explicit_scene_tags=set(),
    )

    assert projection.route_key == expected
    assert projection.fallback_used is False


def test_normalize_retail_is_supported_specialized_domain():
    result = normalize_business_type("retail")

    assert result.canonical_domain == CanonicalBusinessDomain.RETAIL
    assert result.support_status == DomainSupportStatus.SPECIALIZED
    assert result.fallback_reason is None
    assert _tags(result) == {"retail"}
    assert result.business_type == "retail"
    assert result.supported is True


@pytest.mark.parametrize(
    ("value", "hint"),
    [
        ("fitness", "fitness"),
        ("education", "education"),
        ("service", "service"),
        ("professional_service", "professional_service"),
        ("local_service", "local_service"),
        ("home_service", "home_service"),
        ("other", "other"),
    ],
)
def test_normalize_unsupported_domains_preserves_hint(value, hint):
    result = normalize_business_type(value)

    assert result.canonical_domain == CanonicalBusinessDomain.OTHER
    assert result.support_status == DomainSupportStatus.GENERIC_FALLBACK
    assert result.unsupported_domain_hint == hint
    assert result.fallback_reason == DomainFallbackReason.UNSUPPORTED_DOMAIN_IN_MVP
    assert hint in _tags(result)


def test_project_ambiguous_beauty_to_generic_with_reason():
    projection = project_to_legacy_visual_route(
        normalize_business_type("beauty_salon"),
        product_tags=set(),
        explicit_scene_tags=set(),
    )

    assert projection.route_key == LegacyVisualRouteKey.GENERIC
    assert projection.fallback_used is True
    assert projection.fallback_reason == DomainFallbackReason.AMBIGUOUS_BEAUTY_SUBDOMAIN
    assert "ambiguous_beauty_subdomain" in projection.reason_codes


def test_project_retail_to_generic_with_no_visual_profile_reason():
    projection = project_to_legacy_visual_route(
        normalize_business_type("retail"),
        product_tags=set(),
        explicit_scene_tags=set(),
    )

    assert projection.route_key == LegacyVisualRouteKey.GENERIC
    assert projection.fallback_used is True
    assert projection.fallback_reason == DomainFallbackReason.NO_SPECIALIZED_VISUAL_PROFILE
    assert "no_specialized_visual_profile" in projection.reason_codes


def test_project_unsupported_domain_keeps_original_fallback_reason():
    projection = project_to_legacy_visual_route(
        normalize_business_type("fitness"),
        product_tags=set(),
        explicit_scene_tags=set(),
    )

    assert projection.route_key == LegacyVisualRouteKey.GENERIC
    assert projection.fallback_used is True
    assert projection.fallback_reason == DomainFallbackReason.UNSUPPORTED_DOMAIN_IN_MVP
    assert "unsupported_domain_in_mvp" in projection.reason_codes


def test_normalize_unknown_input_is_unresolved_other():
    result = normalize_business_type("spaceship")

    assert result.canonical_domain == CanonicalBusinessDomain.OTHER
    assert result.support_status == DomainSupportStatus.UNRESOLVED
    assert result.fallback_reason == DomainFallbackReason.UNRECOGNIZED_BUSINESS_TYPE
    assert result.clarification_required is True
    assert result.business_type is None


def test_normalize_missing_value_is_unresolved_other():
    result = normalize_business_type(None)

    assert result.canonical_domain == CanonicalBusinessDomain.OTHER
    assert result.support_status == DomainSupportStatus.UNRESOLVED
    assert result.fallback_reason == DomainFallbackReason.UNRECOGNIZED_BUSINESS_TYPE
    assert result.clarification_required is True
    assert result.business_type is None


def test_domain_routing_result_compatibility_properties_are_not_serialized():
    result = normalize_business_type("fitness")

    assert result.canonical == "other"
    assert result.business_type == "fitness"
    assert result.supported is False
    assert result.legacy_fallback_reason == "unsupported_domain_in_mvp"
    dumped = result.model_dump(mode="json")
    assert "business_type" not in dumped
    assert "supported" not in dumped
    assert "canonical" not in dumped
    assert "legacy_fallback_reason" not in dumped


def test_is_supported_domain():
    assert is_supported_domain("cafe")
    assert is_supported_domain("restaurant_bbq")
    assert is_supported_domain("beauty")
    assert is_supported_domain("beauty_salon")
    assert is_supported_domain("retail")
    assert not is_supported_domain("fitness")
    assert not is_supported_domain("other")
    assert not is_supported_domain(None)
