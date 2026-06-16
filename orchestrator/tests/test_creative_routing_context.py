from __future__ import annotations

from typing import get_type_hints

import pytest
from pydantic import ValidationError

from orchestrator.app.llm.creative_routing_context_service import build_creative_routing_context
from orchestrator.app.llm.domain_routing import (
    CanonicalBusinessDomain,
    DomainRoutingResult,
    DomainSupportStatus,
)
from orchestrator.app.llm.ad_format_presets import build_ad_format_spec
from orchestrator.app.schemas.business_context import BusinessEnvironmentContext
from orchestrator.app.schemas.campaign_context import CampaignContext
from orchestrator.app.schemas.creative_routing import CreativeRoutingContext
from orchestrator.app.schemas.input_evidence import EvidenceItem, InputConflict
from orchestrator.app.schemas.llm_marketing import AdFormatSpec
from orchestrator.app.schemas.native_creative import CampaignMessagePlan
from orchestrator.app.schemas.product_understanding import ProductUnderstanding
from orchestrator.app.schemas.product_visual_context import ProductVisualContext


def _domain(domain: CanonicalBusinessDomain = CanonicalBusinessDomain.RETAIL) -> DomainRoutingResult:
    return DomainRoutingResult(
        raw_business_type=domain.value,
        canonical_domain=domain,
        support_status=DomainSupportStatus.SPECIALIZED,
        confidence=0.9,
    )


def _business(domain: CanonicalBusinessDomain = CanonicalBusinessDomain.RETAIL) -> BusinessEnvironmentContext:
    return BusinessEnvironmentContext(broad_domain=domain, confidence=0.8)


def _product(name: str = "desk lamp", path: list[str] | None = None) -> ProductUnderstanding:
    category_path = path or ["home_and_living", "lighting", "desk_lamp"]
    return ProductUnderstanding(
        product_name=name,
        broad_category=category_path[0],
        category_path=category_path,
        confidence=0.86,
    )


def _product_visual(name: str = "desk lamp", path: list[str] | None = None) -> ProductVisualContext:
    return ProductVisualContext(
        product_name=name,
        category_path=path or ["home_and_living", "lighting", "desk_lamp"],
        evidence_refs=["test:product"],
        confidence=0.84,
    )


def _campaign(intent: str = "product_promotion") -> CampaignContext:
    return CampaignContext(
        campaign_intent=intent,
        evidence_refs=["test:campaign"],
        confidence=0.7,
    )


def _context(**overrides) -> CreativeRoutingContext:
    kwargs = {
        "domain": _domain(),
        "business": _business(),
        "product": _product(),
        "product_visual": _product_visual(),
        "campaign": _campaign(),
        "ad_format": build_ad_format_spec("poster"),
        "resolver_version": "visual-strategy-resolver-v1",
    }
    kwargs.update(overrides)
    return build_creative_routing_context(**kwargs)


def _visual_evidence(evidence_id: str) -> EvidenceItem:
    return EvidenceItem(
        evidence_id=evidence_id,
        key="visible_attribute",
        value="brass_finish",
        source="image_vlm",
        evidence_class="visual_observation",
        confidence=0.9,
        usable_for_copy=True,
    )


def _conflict(conflict_id: str) -> InputConflict:
    return InputConflict(
        conflict_id=conflict_id,
        field="product_identity",
        text_value="A",
        image_value="B",
        conflict_type="identity_mismatch",
        severity="manual_review",
        confidence=0.8,
        recommended_resolution="manual_review",
    )


def test_creative_routing_context_fields_are_exact_contract():
    assert set(CreativeRoutingContext.model_fields) == {
        "domain",
        "business",
        "product",
        "product_visual",
        "campaign",
        "ad_format",
        "visual_observations",
        "reference_style_profile",
        "ambiguity_flags",
        "input_conflicts",
        "resolver_version",
    }


def test_nested_contract_annotations_use_expected_types():
    hints = get_type_hints(CreativeRoutingContext)

    assert hints["campaign"] is CampaignContext
    assert hints["ad_format"] is AdFormatSpec


def test_builder_preserves_nested_objects_without_flattening():
    context = _context()

    assert isinstance(context.domain, DomainRoutingResult)
    assert isinstance(context.business, BusinessEnvironmentContext)
    assert isinstance(context.product, ProductUnderstanding)
    assert isinstance(context.product_visual, ProductVisualContext)
    assert isinstance(context.ad_format, AdFormatSpec)
    assert not hasattr(context, "product_name")
    assert not hasattr(context, "campaign_intent")


def test_domain_and_business_domains_must_match():
    with pytest.raises(ValidationError, match="canonical_domain must match"):
        _context(domain=_domain(CanonicalBusinessDomain.BEAUTY), business=_business(CanonicalBusinessDomain.RETAIL))


def test_product_name_must_match_product_visual_name():
    with pytest.raises(ValidationError, match="product_name must match"):
        _context(product=_product("desk lamp"), product_visual=_product_visual("floor lamp"))


def test_category_path_must_match_when_present():
    with pytest.raises(ValidationError, match="category_path must match"):
        _context(product_visual=_product_visual(path=["home_and_living", "different"]))


def test_visual_observations_and_input_conflicts_are_stably_deduplicated():
    e1 = _visual_evidence("e1")
    e2 = _visual_evidence("e2")
    c1 = _conflict("c1")
    c2 = _conflict("c2")

    context = _context(visual_observations=[e1, e2, e1], input_conflicts=[c1, c2, c1])

    assert [item.evidence_id for item in context.visual_observations] == ["e1", "e2"]
    assert [item.conflict_id for item in context.input_conflicts] == ["c1", "c2"]
    assert context.input_conflicts[0].severity == "manual_review"


def test_reference_style_profile_is_json_compatible_and_deep_copied():
    profile = {"style_tags": ["minimal"], "weights": {"soft": 0.8}}
    context = _context(reference_style_profile=profile)
    profile["weights"]["soft"] = 0.1

    assert context.reference_style_profile == {"style_tags": ["minimal"], "weights": {"soft": 0.8}}
    with pytest.raises(ValidationError, match="JSON-compatible"):
        _context(reference_style_profile={"bad": object()})


def test_ambiguity_flags_and_resolver_version_are_normalized():
    context = _context(ambiguity_flags=[" beauty_subdomain ", "beauty_subdomain", "", "format_unclear"], resolver_version=" v1 ")

    assert context.ambiguity_flags == ["beauty_subdomain", "format_unclear"]
    assert context.resolver_version == "v1"
    for bad_version in ("", " ", 1, True, None):
        with pytest.raises(ValidationError):
            _context(resolver_version=bad_version)


def test_campaign_message_plan_is_not_campaign_context():
    plan = CampaignMessagePlan(
        campaign_role="new_product_introduction",
        primary_communication_goal="new_product_launch",
        funnel_stage="awareness",
        image_explanatory_power=0.7,
        verified_information_density="low",
        visible_copy_mode="headline_plus_support",
        headline_function="launch_announcement",
        support_function="launch_context",
        rationale=[],
        confidence=0.8,
    )

    with pytest.raises(ValidationError):
        _context(campaign=plan)
    assert "visible_copy_mode" not in CampaignContext.model_fields
    assert "headline_function" not in CampaignContext.model_fields
    assert "support_function" not in CampaignContext.model_fields


def test_ad_format_spec_is_reused_and_not_copied_into_campaign():
    context = _context(ad_format=build_ad_format_spec("instagram_story"))

    assert context.ad_format.ad_format == "instagram_story"
    assert "AdFormatContract" not in globals()
    assert not hasattr(context.campaign, "ad_format")
    assert "campaign_intent" not in context.ad_format.metadata


def test_metamorphic_business_change_preserves_other_contexts():
    original = _context()
    changed = _context(domain=_domain(CanonicalBusinessDomain.BEAUTY), business=_business(CanonicalBusinessDomain.BEAUTY))

    assert changed.product == original.product
    assert changed.product_visual == original.product_visual
    assert changed.campaign == original.campaign
    assert changed.ad_format == original.ad_format


def test_metamorphic_product_change_preserves_non_product_contexts():
    original = _context()
    changed = _context(
        product=_product("floor lamp", ["home_and_living", "lighting", "floor_lamp"]),
        product_visual=_product_visual("floor lamp", ["home_and_living", "lighting", "floor_lamp"]),
    )

    assert changed.domain == original.domain
    assert changed.business == original.business
    assert changed.campaign == original.campaign
    assert changed.ad_format == original.ad_format


def test_metamorphic_campaign_or_ad_format_change_preserves_other_contexts():
    original = _context()
    campaign_changed = _context(campaign=_campaign("seasonal_launch"))
    format_changed = _context(ad_format=build_ad_format_spec("banner"))

    assert campaign_changed.domain == original.domain
    assert campaign_changed.product_visual == original.product_visual
    assert campaign_changed.ad_format == original.ad_format
    assert format_changed.domain == original.domain
    assert format_changed.product == original.product
    assert format_changed.campaign == original.campaign
