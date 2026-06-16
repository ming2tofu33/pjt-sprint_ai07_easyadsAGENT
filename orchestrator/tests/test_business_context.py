from __future__ import annotations

import pytest
from pydantic import ValidationError

from orchestrator.app.llm.business_context_service import build_business_environment_context
from orchestrator.app.llm.domain_routing import (
    CanonicalBusinessDomain,
    DomainFallbackReason,
    DomainRoutingResult,
    DomainSupportStatus,
    RoutingEvidenceSource,
    RoutingTagEvidence,
)
from orchestrator.app.schemas.business_context import BusinessEnvironmentContext


def _domain_result(
    domain: CanonicalBusinessDomain,
    *,
    confidence: float = 0.8,
) -> DomainRoutingResult:
    if domain == CanonicalBusinessDomain.OTHER:
        return DomainRoutingResult(
            raw_business_type="fitness",
            canonical_domain=domain,
            support_status=DomainSupportStatus.GENERIC_FALLBACK,
            unsupported_domain_hint="fitness",
            fallback_reason=DomainFallbackReason.UNSUPPORTED_DOMAIN_IN_MVP,
            confidence=confidence,
        )
    return DomainRoutingResult(
        raw_business_type=domain.value,
        canonical_domain=domain,
        support_status=DomainSupportStatus.SPECIALIZED,
        confidence=confidence,
    )


def test_schema_fields_are_exact_boundary_contract():
    assert set(BusinessEnvironmentContext.model_fields) == {
        "broad_domain",
        "venue_type",
        "service_model",
        "business_tags",
        "environment_tags",
        "evidence_refs",
        "confidence",
    }


def test_schema_uses_canonical_business_domain_and_allows_confidence_bounds():
    low = BusinessEnvironmentContext(
        broad_domain=CanonicalBusinessDomain.FOOD_AND_BEVERAGE,
        confidence=0.0,
    )
    high = BusinessEnvironmentContext(
        broad_domain=CanonicalBusinessDomain.RETAIL,
        confidence=1.0,
    )

    assert low.broad_domain is CanonicalBusinessDomain.FOOD_AND_BEVERAGE
    assert high.confidence == 1.0


@pytest.mark.parametrize("confidence", [-0.01, 1.01])
def test_confidence_out_of_range_is_rejected(confidence: float):
    with pytest.raises(ValidationError):
        BusinessEnvironmentContext(
            broad_domain=CanonicalBusinessDomain.RETAIL,
            confidence=confidence,
        )


@pytest.mark.parametrize(
    "field_name,value",
    [
        ("product_name", "감자튀김"),
        ("cooking_method", "fried"),
        ("preset_id", "preset_food"),
        ("template_id", "template_food"),
        ("headline", "New menu"),
    ],
)
def test_forbidden_extra_fields_are_rejected(field_name: str, value: str):
    with pytest.raises(ValidationError):
        BusinessEnvironmentContext(
            broad_domain=CanonicalBusinessDomain.FOOD_AND_BEVERAGE,
            confidence=0.9,
            **{field_name: value},
        )


def test_json_round_trip_preserves_contract_values():
    context = BusinessEnvironmentContext(
        broad_domain=CanonicalBusinessDomain.BEAUTY,
        venue_type="beauty_salon",
        service_model="appointment",
        business_tags=["hair_salon"],
        environment_tags=["private_room"],
        evidence_refs=["user_text:salon"],
        confidence=0.7,
    )

    restored = BusinessEnvironmentContext.model_validate_json(context.model_dump_json())

    assert restored == context


def test_context_is_frozen():
    context = BusinessEnvironmentContext(
        broad_domain=CanonicalBusinessDomain.RETAIL,
        confidence=0.9,
    )

    with pytest.raises(ValidationError):
        context.confidence = 0.1


def test_open_vocabulary_fields_are_normalized_without_closing_taxonomy():
    context = BusinessEnvironmentContext(
        broad_domain=CanonicalBusinessDomain.FOOD_AND_BEVERAGE,
        venue_type="  hotel_brunch_restaurant ",
        service_model=" private_booking ",
        business_tags=["korean_bbq", " korean_bbq ", "", "dine_in"],
        environment_tags=["warm_interior", "restaurant_table", "warm_interior", " "],
        evidence_refs=["user_text:고깃집"],
        confidence=0.97,
    )

    assert context.venue_type == "hotel_brunch_restaurant"
    assert context.service_model == "private_booking"
    assert context.business_tags == ["korean_bbq", "dine_in"]
    assert context.environment_tags == ["warm_interior", "restaurant_table"]


@pytest.mark.parametrize(
    "field_name,value",
    [
        ("venue_type", 123),
        ("service_model", True),
        ("business_tags", ["valid", 123]),
        ("environment_tags", [{"unexpected": "value"}]),
        ("evidence_refs", [object()]),
    ],
)
def test_non_string_open_context_values_are_rejected(field_name: str, value: object):
    with pytest.raises(ValidationError):
        BusinessEnvironmentContext(
            broad_domain=CanonicalBusinessDomain.RETAIL,
            confidence=0.8,
            **{field_name: value},
        )


def test_specific_environment_requires_evidence_refs():
    with pytest.raises(ValidationError, match="specific business environment fields require evidence_refs"):
        BusinessEnvironmentContext(
            broad_domain=CanonicalBusinessDomain.FOOD_AND_BEVERAGE,
            venue_type="korean_bbq_restaurant",
            business_tags=["korean_bbq"],
            confidence=0.97,
        )


@pytest.mark.parametrize(
    "field_name,value",
    [
        ("venue_type", "local_store"),
        ("service_model", "appointment"),
        ("business_tags", ["local_business"]),
        ("environment_tags", ["warm_interior"]),
    ],
)
def test_each_specific_environment_field_requires_evidence(field_name: str, value: str | list[str]):
    with pytest.raises(ValidationError, match="specific business environment fields require evidence_refs"):
        BusinessEnvironmentContext(
            broad_domain=CanonicalBusinessDomain.RETAIL,
            confidence=0.8,
            **{field_name: value},
        )


def test_specific_environment_with_evidence_is_allowed_and_evidence_is_normalized():
    context = BusinessEnvironmentContext(
        broad_domain=CanonicalBusinessDomain.FOOD_AND_BEVERAGE,
        venue_type="korean_bbq_restaurant",
        business_tags=["korean_bbq"],
        evidence_refs=["user_text:고깃집", " user_text:고깃집 ", "", "reference_image:warm_wood_interior"],
        confidence=0.97,
    )

    assert context.evidence_refs == ["user_text:고깃집", "reference_image:warm_wood_interior"]


def test_broad_domain_only_does_not_require_evidence_refs():
    context = BusinessEnvironmentContext(
        broad_domain=CanonicalBusinessDomain.RETAIL,
        confidence=0.78,
    )

    assert context.evidence_refs == []


@pytest.mark.parametrize("domain", list(CanonicalBusinessDomain))
def test_builder_preserves_a1_canonical_domain(domain: CanonicalBusinessDomain):
    domain_result = _domain_result(domain)

    context = build_business_environment_context(domain_result)

    assert context.broad_domain is domain
    assert context.venue_type is None
    assert context.business_tags == []
    assert context.environment_tags == []


def test_builder_does_not_auto_copy_domain_result_business_tags():
    domain_result = DomainRoutingResult(
        raw_business_type="restaurant_bbq",
        canonical_domain=CanonicalBusinessDomain.FOOD_AND_BEVERAGE,
        support_status=DomainSupportStatus.SPECIALIZED,
        business_tags=[
            RoutingTagEvidence(
                tag="restaurant",
                source=RoutingEvidenceSource.LEGACY_ALIAS,
                confidence=1.0,
            ),
            RoutingTagEvidence(
                tag="korean_bbq",
                source=RoutingEvidenceSource.LEGACY_ALIAS,
                confidence=1.0,
            ),
        ],
        confidence=0.95,
    )

    context = build_business_environment_context(domain_result)

    assert context.broad_domain == CanonicalBusinessDomain.FOOD_AND_BEVERAGE
    assert context.business_tags == []
    assert context.evidence_refs == []


def test_builder_uses_explicit_confidence_or_domain_result_confidence():
    domain_result = _domain_result(CanonicalBusinessDomain.RETAIL, confidence=0.42)

    default_context = build_business_environment_context(domain_result)
    explicit_context = build_business_environment_context(domain_result, confidence=0.99)

    assert default_context.confidence == 0.42
    assert explicit_context.confidence == 0.99


def test_builder_does_not_infer_product_or_visual_strategy_from_korean_bbq_context():
    domain_result = _domain_result(CanonicalBusinessDomain.FOOD_AND_BEVERAGE, confidence=0.97)

    context = build_business_environment_context(
        domain_result,
        venue_type="korean_bbq_restaurant",
        business_tags=["korean_bbq"],
        evidence_refs=["user_text:고깃집"],
    )
    dumped = context.model_dump()
    serialized = context.model_dump_json()

    assert dumped["venue_type"] == "korean_bbq_restaurant"
    assert dumped["business_tags"] == ["korean_bbq"]
    assert "preset_id" not in dumped
    assert "template_id" not in dumped
    for forbidden in ("감자튀김", "fried", "grill", "charcoal", "open_flame", "meat"):
        assert forbidden not in serialized
