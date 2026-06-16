"""Phase 0 contract tests for business_type -> visual/copy routing.

These tests do not assert that any taxonomy is "good" — they make the structural
risks documented in docs/PRESET_ROUTING_AUDIT.md visible and regression-proof:

  * P5  preset.business_type must always be a valid ScenePlan BusinessType
        (issue 7 was a runtime pydantic crash from a preset whose business_type
        was not in the ScenePlan Literal).
  * P6  ambiguous `beauty_salon` must not silently route to the hair preset.
  * Copy alias: plain `restaurant` copy must not be forced into the bbq tone.
  * P4  every BriefBusinessType the LLM can emit must either route to a domain
        or leave an observable generic-fallback breadcrumb (never evaporate
        silently).

A-2 changes the canonical domain model to food_and_beverage / beauty / retail /
other, while leaving the legacy visual selector path in place until later A
phases. Legacy visual gaps are still asserted explicitly so any production
selector change is deliberate.
"""

from __future__ import annotations

from typing import get_args

import pytest

# Import the graph package first to fully initialise the graph<->brief_interpreter
# import chain before importing brief_interpreter directly (avoids a pre-existing
# circular-import error when brief_interpreter is the first module loaded).
import orchestrator.app.graph.nodes  # noqa: F401

from orchestrator.app.llm.copy_tone_policy import get_copy_tone_policy, resolve_copy_route_key
from orchestrator.app.llm.domain_routing import (
    CANONICAL_DOMAINS,
    CanonicalBusinessDomain,
    DomainFallbackReason,
    DomainRoutingResult,
    DomainSupportStatus,
    LegacyRoutingProjection,
    LegacyVisualRouteKey,
    ReferenceTemplateRoutingProfile,
    RoutingEvidenceSource,
    RoutingTagEvidence,
    SUPPORTED_DOMAINS,
    normalize_business_type,
    project_to_legacy_visual_route,
    to_canonical_domain,
)
from orchestrator.app.llm.scene_planner import build_scene_plan
from orchestrator.app.llm.nodes.brief_interpreter import (
    BUSINESS_TYPE_MAP,
    build_context_updates_from_brief_interpreter,
)
from orchestrator.app.llm.option_registry import OPTION_QUESTION_REGISTRY
from orchestrator.app.llm.schemas.image_prompt_v3 import BusinessType as ScenePlanBusinessType
from orchestrator.app.llm.visual_presets import (
    PRESET_ID_BY_BUSINESS_TYPE,
    VISUAL_PRESETS,
    select_visual_preset,
)
from orchestrator.app.llm.visual_templates import select_visual_template
from orchestrator.app.schemas.brief_llm import BriefBusinessType, BriefInterpreterOutput

SCENEPLAN_BUSINESS_TYPES = set(get_args(ScenePlanBusinessType))


# --- A-1: v1 contract type cluster ------------------------------------------


def test_a1_canonical_business_domain_is_mvp_3_plus_other():
    assert {item.value for item in CanonicalBusinessDomain} == {
        "food_and_beverage",
        "beauty",
        "retail",
        "other",
    }


def test_a1_legacy_visual_route_keys_match_current_compatibility_routes():
    assert {item.value for item in LegacyVisualRouteKey} == {
        "cafe",
        "restaurant",
        "restaurant_bbq",
        "beauty_skincare",
        "beauty_hair",
        "beauty_nail",
        "beauty_spa",
        "generic",
    }


def test_a1_domain_routing_result_allows_specialized_without_fallback():
    result = DomainRoutingResult(
        raw_business_type="cafe",
        canonical_domain=CanonicalBusinessDomain.FOOD_AND_BEVERAGE,
        support_status=DomainSupportStatus.SPECIALIZED,
        business_tags=[
            RoutingTagEvidence(
                tag="cafe",
                source=RoutingEvidenceSource.USER_TEXT,
                confidence=0.99,
            )
        ],
        confidence=0.99,
    )

    assert result.contract_version == "1.0"
    assert result.fallback_reason is None
    assert result.clarification_required is False


def test_a1_domain_routing_result_requires_fallback_reason_for_non_specialized():
    with pytest.raises(ValueError, match="non-specialized routing requires fallback_reason"):
        DomainRoutingResult(
            raw_business_type="fitness",
            canonical_domain=CanonicalBusinessDomain.OTHER,
            support_status=DomainSupportStatus.GENERIC_FALLBACK,
            confidence=0.9,
        )


def test_a1_domain_routing_result_requires_clarification_for_needs_evidence():
    with pytest.raises(ValueError, match="needs_evidence/unresolved must require clarification"):
        DomainRoutingResult(
            raw_business_type="beauty_salon",
            canonical_domain=CanonicalBusinessDomain.BEAUTY,
            support_status=DomainSupportStatus.NEEDS_EVIDENCE,
            fallback_reason=DomainFallbackReason.AMBIGUOUS_BEAUTY_SUBDOMAIN,
            clarification_required=False,
            confidence=0.8,
        )


def test_a1_unsupported_domain_hint_is_only_valid_for_other():
    with pytest.raises(ValueError, match="unsupported_domain_hint is only valid for OTHER"):
        DomainRoutingResult(
            raw_business_type="fitness",
            canonical_domain=CanonicalBusinessDomain.RETAIL,
            support_status=DomainSupportStatus.GENERIC_FALLBACK,
            unsupported_domain_hint="fitness",
            fallback_reason=DomainFallbackReason.UNSUPPORTED_DOMAIN_IN_MVP,
            confidence=0.8,
        )


def test_a1_routing_tag_evidence_rejects_unsafe_tag_values():
    with pytest.raises(ValueError):
        RoutingTagEvidence(
            tag="Bad Tag",
            source=RoutingEvidenceSource.USER_TEXT,
            confidence=0.5,
        )


def test_a1_reference_template_profile_requires_routing_dimension():
    with pytest.raises(ValueError, match="routing profile requires at least one routing dimension"):
        ReferenceTemplateRoutingProfile()


def test_a1_reference_template_profile_all_domains_can_be_empty_otherwise():
    profile = ReferenceTemplateRoutingProfile(applies_to_all_domains=True)

    assert profile.applies_to_all_domains is True
    assert profile.business_domains == set()


def test_a1_reference_template_profile_rejects_overlapping_included_and_excluded_tags():
    with pytest.raises(ValueError, match="included and excluded tags must not overlap"):
        ReferenceTemplateRoutingProfile(
            business_domains={CanonicalBusinessDomain.FOOD_AND_BEVERAGE},
            business_tags={"cafe"},
            excluded_tags={"cafe"},
        )


def test_a1_legacy_projection_is_deprecated_compatibility_result():
    projection = LegacyRoutingProjection(
        route_key=LegacyVisualRouteKey.GENERIC,
        fallback_used=True,
        fallback_reason=DomainFallbackReason.NO_SPECIALIZED_VISUAL_PROFILE,
        reason_codes=["no_specialized_visual_profile"],
    )

    assert projection.projection_version == "1.0"
    assert projection.deprecated is True

# The business_type values that are fully resolved legacy route keys and round
# trip identically through the preset selector. Ambiguous aliases beauty_salon /
# beauty intentionally fail closed to generic in A-4.
CANONICAL_BUSINESS_TYPES = {
    "cafe",
    "restaurant_bbq",
    "restaurant",
    "beauty_skincare",
    "beauty_hair",
    "beauty_nail",
    "beauty_spa",
    "generic",
}


# --- P5: preset.business_type ⊆ ScenePlan Literal (issue 7 crash guard) -------

def test_all_preset_business_types_are_valid_sceneplan_literals():
    for preset_id, preset in VISUAL_PRESETS.items():
        bt = preset["business_type"]
        assert bt in SCENEPLAN_BUSINESS_TYPES, (
            f"preset {preset_id!r} has business_type {bt!r} which is not a valid "
            f"ScenePlan BusinessType {sorted(SCENEPLAN_BUSINESS_TYPES)} -> ScenePlan "
            f"construction would raise pydantic ValidationError at runtime (issue 7)."
        )


def test_a7_sceneplan_business_type_excludes_ambiguous_beauty_salon():
    assert "beauty_salon" not in SCENEPLAN_BUSINESS_TYPES


def test_preset_dict_keys_match_their_preset_id():
    for preset_id, preset in VISUAL_PRESETS.items():
        assert preset["preset_id"] == preset_id


def test_preset_id_mapping_points_at_real_presets():
    for business_type, preset_id in PRESET_ID_BY_BUSINESS_TYPE.items():
        assert preset_id in VISUAL_PRESETS, f"{business_type!r} -> missing preset {preset_id!r}"


def test_a7_every_legacy_visual_route_key_has_preset_template_and_sceneplan_inventory():
    for route_key in LegacyVisualRouteKey:
        key = route_key.value
        preset = select_visual_preset(key)
        template = select_visual_template(key, "instagram_feed", "premium", None)
        scene_plan = build_scene_plan(
            user_input="",
            business_type=key,
            ad_format="instagram_feed",
            metadata={
                "business_type": key,
                "item_or_service": "대표 상품",
                "target_persona": None,
                "promotion_goal": "brand_awareness",
            },
        )

        assert preset["business_type"] == key
        assert preset["preset_id"] in VISUAL_PRESETS
        assert key in template.business_types
        assert key in SCENEPLAN_BUSINESS_TYPES
        assert scene_plan.business_type == key


def test_canonical_business_types_round_trip_through_selector():
    for business_type in CANONICAL_BUSINESS_TYPES:
        preset = select_visual_preset(business_type)
        assert preset["business_type"] == business_type


# --- A-4: selectors must fail closed for ambiguous/raw values ----------------

def test_beauty_salon_routes_to_generic_until_subtype_evidence_exists():
    preset = select_visual_preset("beauty_salon")
    assert preset["business_type"] == "generic"
    assert preset["preset_id"] == "generic_clean_ad_background"


def test_ambiguous_beauty_routes_to_generic():
    preset = select_visual_preset("beauty")
    assert preset["business_type"] == "generic"
    assert preset["preset_id"] == "generic_clean_ad_background"


def test_explicit_beauty_subtypes_still_route_correctly():
    assert select_visual_preset("beauty_hair")["business_type"] == "beauty_hair"
    assert select_visual_preset("beauty_nail")["business_type"] == "beauty_nail"
    assert select_visual_preset("beauty_spa")["business_type"] == "beauty_spa"


def test_raw_korean_bbq_input_no_longer_routes_by_keyword_to_bbq():
    preset = select_visual_preset("숯불 삼겹살 맛집")
    assert preset["business_type"] == "generic"
    assert preset["preset_id"] == "generic_clean_ad_background"


def test_legacy_projection_is_the_only_place_that_can_select_bbq_visual_route():
    projection = project_to_legacy_visual_route(
        normalize_business_type("restaurant_bbq"),
        product_tags=set(),
        explicit_scene_tags=set(),
    )

    assert projection.route_key == LegacyVisualRouteKey.RESTAURANT
    assert projection.route_key != LegacyVisualRouteKey.RESTAURANT_BBQ


def test_legacy_projection_selects_bbq_only_with_visual_evidence():
    projection = project_to_legacy_visual_route(
        normalize_business_type("restaurant_bbq"),
        product_tags={"grilled_meat"},
        explicit_scene_tags=set(),
    )

    assert projection.route_key == LegacyVisualRouteKey.RESTAURANT_BBQ


# --- Copy alias: plain restaurant must not be forced into bbq tone -----------

def test_plain_restaurant_copy_is_not_aliased_to_bbq():
    policy = get_copy_tone_policy("restaurant")
    assert policy["business_type"] != "restaurant_bbq"
    assert policy["business_type"] == "generic"


@pytest.mark.parametrize(
    "business_type",
    ["restaurant", "restaurant_bbq", "bbq", "meat_restaurant", "korean_food"],
)
def test_a6_restaurant_and_bbq_like_copy_inputs_use_neutral_policy(business_type):
    assert resolve_copy_route_key(business_type) == "generic"

    policy = get_copy_tone_policy(business_type)

    assert policy["policy_id"] == "generic_v1"
    assert policy["business_type"] == "generic"


@pytest.mark.parametrize("business_type", ["beauty", "beauty_salon", "salon"])
def test_a6_ambiguous_beauty_copy_inputs_use_neutral_policy(business_type):
    assert resolve_copy_route_key(business_type) == "generic"

    policy = get_copy_tone_policy(business_type)

    assert policy["policy_id"] == "generic_v1"
    assert policy["business_type"] == "generic"


@pytest.mark.parametrize(
    ("business_type", "route_key", "policy_id"),
    [
        ("beauty_skincare", "beauty_skincare", "beauty_skincare_v1"),
        ("skincare", "beauty_skincare", "beauty_skincare_v1"),
        ("beauty_hair", "beauty_hair", "beauty_hair_v1"),
        ("hair", "beauty_hair", "beauty_hair_v1"),
        ("beauty_nail", "beauty_nail", "beauty_nail_v1"),
        ("nail", "beauty_nail", "beauty_nail_v1"),
        ("beauty_spa", "beauty_spa", "beauty_spa_v1"),
        ("spa", "beauty_spa", "beauty_spa_v1"),
    ],
)
def test_a6_exact_beauty_subtype_copy_inputs_still_use_specialized_policy(
    business_type,
    route_key,
    policy_id,
):
    assert resolve_copy_route_key(business_type) == route_key

    policy = get_copy_tone_policy(business_type)

    assert policy["policy_id"] == policy_id


# --- P4: BriefBusinessType routing table (no silent evaporation) -------------

def test_a7_business_type_option_registry_values_have_explicit_routing_contract():
    question = OPTION_QUESTION_REGISTRY["business_type"]
    actual = {}

    for option in question.options:
        result = normalize_business_type(option.value)
        actual[option.value] = (
            result.canonical_domain.value,
            result.support_status.value,
            result.unsupported_domain_hint,
            result.fallback_reason.value if result.fallback_reason else None,
            result.business_type,
            sorted(tag.tag for tag in result.business_tags),
            result.matched_aliases,
        )

    assert actual == {
        "restaurant": ("food_and_beverage", "specialized", None, None, "restaurant", ["restaurant"], ["restaurant"]),
        "cafe": ("food_and_beverage", "specialized", None, None, "cafe", ["cafe"], ["cafe"]),
        "beauty_salon": (
            "beauty",
            "needs_evidence",
            None,
            "ambiguous_beauty_subdomain",
            None,
            ["beauty_service"],
            ["beauty_salon"],
        ),
        "bar": ("other", "generic_fallback", "bar", "unsupported_domain_in_mvp", "bar", ["bar"], ["bar"]),
        "fitness": (
            "other",
            "generic_fallback",
            "fitness",
            "unsupported_domain_in_mvp",
            "fitness",
            ["fitness"],
            ["fitness"],
        ),
        "academy": (
            "other",
            "generic_fallback",
            "education",
            "unsupported_domain_in_mvp",
            "education",
            ["academy", "education"],
            ["academy"],
        ),
        "flower_shop": (
            "retail",
            "specialized",
            None,
            None,
            "retail",
            ["flower_shop", "retail"],
            ["flower_shop"],
        ),
        "store": ("retail", "specialized", None, None, "retail", ["physical_store", "retail"], ["store"]),
        "custom": ("other", "unresolved", None, "unrecognized_business_type", None, [], []),
    }


def test_every_brief_business_type_is_routed_or_observably_fellback():
    # The domain-routing SSOT is the oracle; brief_interpreter must agree with it,
    # and every unsupported/unknown domain must leave an observable breadcrumb.
    for value in get_args(BriefBusinessType):
        normalized = normalize_business_type(value)
        output = BriefInterpreterOutput(business_type=value)
        updates, warnings = build_context_updates_from_brief_interpreter(output)

        if normalized.business_type is not None:
            assert updates.get("business_type") == normalized.business_type
        else:
            assert "business_type" not in updates

        if not normalized.supported:
            # fitness/retail/education/service/other -> generic, but never silent.
            assert any("business_type_fallback_generic" in w for w in warnings), (
                f"{value!r} evaporated silently — expected a generic-fallback warning."
            )


def test_retail_brief_business_type_is_not_silently_dropped():
    normalized = normalize_business_type("retail")
    updates, warnings = build_context_updates_from_brief_interpreter(
        BriefInterpreterOutput(business_type="retail")
    )

    assert normalized.canonical_domain == CanonicalBusinessDomain.RETAIL
    assert normalized.support_status == DomainSupportStatus.SPECIALIZED
    assert normalized.business_type == "retail"
    assert updates.get("business_type") == "retail"
    assert not any("business_type_fallback_generic" in warning for warning in warnings)


@pytest.mark.parametrize("value", ["fitness", "education", "service", "other"])
def test_unsupported_brief_business_type_preserves_hint_and_warning(value):
    normalized = normalize_business_type(value)
    updates, warnings = build_context_updates_from_brief_interpreter(
        BriefInterpreterOutput(business_type=value)
    )

    assert normalized.canonical_domain == CanonicalBusinessDomain.OTHER
    assert normalized.support_status == DomainSupportStatus.GENERIC_FALLBACK
    assert normalized.unsupported_domain_hint == value
    assert normalized.fallback_reason == DomainFallbackReason.UNSUPPORTED_DOMAIN_IN_MVP
    assert updates.get("business_type") == value
    assert any("business_type_fallback_generic: unsupported_domain_in_mvp" in warning for warning in warnings)


def test_business_type_map_is_derived_from_ssot():
    for domain, business_type in BUSINESS_TYPE_MAP.items():
        assert normalize_business_type(domain).business_type == business_type


def test_supported_domains_are_a_declared_subset_of_canonical():
    assert SUPPORTED_DOMAINS <= CANONICAL_DOMAINS
    assert CANONICAL_DOMAINS == {"food_and_beverage", "beauty", "retail", "other"}
    assert SUPPORTED_DOMAINS == {"food_and_beverage", "beauty", "retail"}


# --- Known legacy visual gaps documented as explicit assertions --------------

@pytest.mark.parametrize("business_type", ["fitness", "retail", "education", "service"])
def test_unsupported_domains_currently_resolve_to_generic_preset(business_type):
    # KNOWN GAP (Phase 4): these have no visual strategy yet and fall to generic.
    # Asserted so the gap is visible and any future support is a deliberate change.
    assert select_visual_preset(business_type)["business_type"] == "generic"


# --- P2: preset and template must agree on the domain family -----------------

@pytest.mark.parametrize("business_type", ["cafe", "restaurant_bbq", "restaurant", "beauty_salon"])
def test_preset_and_template_share_domain_family(business_type):
    preset = select_visual_preset(business_type)
    template = select_visual_template(business_type, "instagram_feed", None)
    # Family judged in one place via the SSOT classifier.
    preset_family = to_canonical_domain(preset["business_type"])
    template_family = to_canonical_domain(template.business_types[0])
    assert preset_family == template_family, (
        f"{business_type!r}: preset -> {preset['business_type']!r} ({preset_family}) but "
        f"template -> {template.template_id!r} ({template_family}); different domain families."
    )
