from __future__ import annotations

import pytest

from orchestrator.app.llm.ad_format_presets import build_ad_format_spec
from orchestrator.app.llm.domain_routing import CanonicalBusinessDomain, DomainRoutingResult, DomainSupportStatus
from orchestrator.app.llm.visual_strategy_resolver import (
    NoEligibleVisualStrategyError,
    VisualStrategyRuntimeContextConflictError,
    build_visual_strategy_signal_snapshot,
    resolve_visual_strategy,
)
from orchestrator.app.llm.visual_strategy_profiles import build_default_visual_strategy_registry
from orchestrator.app.llm.visual_strategy_registry import VisualStrategyRegistry
from orchestrator.app.schemas.business_context import BusinessEnvironmentContext
from orchestrator.app.schemas.campaign_context import CampaignContext
from orchestrator.app.schemas.creative_routing import CreativeRoutingContext
from orchestrator.app.schemas.product_understanding import ProductUnderstanding
from orchestrator.app.schemas.product_visual_context import ProductVisualContext
from orchestrator.app.schemas.visual_semantic_intent import VisualSemanticIntent
from orchestrator.app.schemas.visual_strategy import (
    VisualElementEvidenceRequirement,
    VisualStrategyContextSource,
    VisualStrategyProfile,
    VisualStrategyResourceCatalog,
    VisualStrategyTagRequirement,
)
from orchestrator.app.schemas.visual_strategy_resolution import VisualStrategyRejectionCode, VisualStrategyRuntimeContext


def _resources() -> VisualStrategyResourceCatalog:
    return VisualStrategyResourceCatalog(
        composition_template_ids=["template_alpha"],
        mood_preset_ids=["preset_alpha"],
        copy_tone_profile_ids=["tone_alpha"],
        provider_capability_ids=None,
    )


def _profile(**overrides) -> VisualStrategyProfile:
    data = {
        "strategy_id": "profile_alpha",
        "archetype": "archetype_alpha",
        "supported_domains": [CanonicalBusinessDomain.RETAIL],
        "composition_template_id": "template_alpha",
        "mood_preset_id": "preset_alpha",
        "copy_tone_profile_id": "tone_alpha",
        "priority": 10,
        "enabled": True,
    }
    data.update(overrides)
    return VisualStrategyProfile(**data)


def _registry(*profiles: VisualStrategyProfile) -> VisualStrategyRegistry:
    return VisualStrategyRegistry(version="registry-v1", profiles=profiles, resources=_resources())


def _context(
    *,
    canonical_domain: CanonicalBusinessDomain = CanonicalBusinessDomain.RETAIL,
    business_tags: list[str] | None = None,
    product_tags: list[str] | None = None,
    preparation_methods: list[str] | None = None,
    permissible_inferences: list[str] | None = None,
    prohibited_inferences: list[str] | None = None,
    placement: str = "poster",
) -> CreativeRoutingContext:
    domain_result = DomainRoutingResult(
        raw_business_type=canonical_domain.value,
        canonical_domain=canonical_domain,
        support_status=DomainSupportStatus.SPECIALIZED,
        confidence=0.9,
    )
    return CreativeRoutingContext(
        domain=domain_result,
        business=BusinessEnvironmentContext(
            broad_domain=canonical_domain,
            business_tags=business_tags or [],
            evidence_refs=["test:business"] if business_tags else [],
            confidence=0.8,
        ),
        product=ProductUnderstanding(
            product_name="synthetic product",
            broad_category="home_and_living",
            category_path=["home_and_living", "synthetic_product"],
            normalized_product_type="synthetic_product",
            confidence=0.8,
        ),
        product_visual=ProductVisualContext(
            product_name="synthetic product",
            category_path=["home_and_living", "synthetic_product"],
            product_tags=product_tags or [],
            explicit_preparation_methods=preparation_methods or [],
            permissible_visual_inferences=permissible_inferences or [],
            prohibited_visual_inferences=prohibited_inferences or [],
            evidence_refs=["test:product"],
            confidence=0.8,
        ),
        campaign=CampaignContext(confidence=0.8),
        ad_format=build_ad_format_spec(placement),
        resolver_version="resolver-test",
    )


def _intent(**overrides) -> VisualSemanticIntent:
    data = {
        "subject_priority": 0.8,
        "environment_priority": 0.7,
        "text_priority": 0.5,
        "copy_presence_mode": "copy_optional",
        "confidence": 0.8,
    }
    data.update(overrides)
    return VisualSemanticIntent(**data)


def _source_gated_profile() -> VisualStrategyProfile:
    return _profile(
        strategy_id="source_gated_profile",
        required_tag_requirements=(
            VisualStrategyTagRequirement(
                source=VisualStrategyContextSource.BUSINESS,
                all_of=["business_signal_alpha"],
            ),
            VisualStrategyTagRequirement(
                source=VisualStrategyContextSource.PRODUCT_VISUAL_FACT,
                all_of=["product_signal_beta"],
            ),
        ),
    )


def _fallback_profile(**overrides) -> VisualStrategyProfile:
    return _profile(
        strategy_id=overrides.pop("strategy_id", "fallback_profile"),
        fallback_tier=overrides.pop("fallback_tier", 1),
        priority=overrides.pop("priority", 1),
        **overrides,
    )


def _element_requirement(
    *,
    element: str = "visual_element_alpha",
    source: VisualStrategyContextSource = VisualStrategyContextSource.PRODUCT_VISUAL_FACT,
    tag: str = "product_signal_beta",
) -> VisualElementEvidenceRequirement:
    return VisualElementEvidenceRequirement(
        element=element,
        requirements=(VisualStrategyTagRequirement(source=source, all_of=[tag]),),
    )


def test_business_only_source_requirement_does_not_pass_product_requirement():
    registry = _registry(_source_gated_profile(), _fallback_profile())

    decision = resolve_visual_strategy(
        _context(business_tags=["business_signal_alpha"]),
        _intent(),
        registry,
    )

    assert decision.strategy_id == "fallback_profile"
    source_trace = next(item for item in decision.trace.candidates if item.strategy_id == "source_gated_profile")
    assert VisualStrategyRejectionCode.MISSING_SOURCE_REQUIREMENT in source_trace.rejection_codes


def test_product_only_source_requirement_does_not_pass_business_requirement():
    registry = _registry(_source_gated_profile(), _fallback_profile())

    decision = resolve_visual_strategy(
        _context(product_tags=["product_signal_beta"]),
        _intent(),
        registry,
    )

    assert decision.strategy_id == "fallback_profile"
    source_trace = next(item for item in decision.trace.candidates if item.strategy_id == "source_gated_profile")
    assert VisualStrategyRejectionCode.MISSING_SOURCE_REQUIREMENT in source_trace.rejection_codes


def test_business_and_product_requirements_make_specialized_profile_eligible():
    registry = _registry(_source_gated_profile(), _fallback_profile(priority=100))

    decision = resolve_visual_strategy(
        _context(business_tags=["business_signal_alpha"], product_tags=["product_signal_beta"]),
        _intent(),
        registry,
    )

    assert decision.strategy_id == "source_gated_profile"
    assert decision.fallback_used is False
    assert decision.composition_template_id == "template_alpha"
    assert decision.registry_version == registry.version
    assert decision.registry_snapshot_hash == registry.snapshot_hash


def test_prohibited_visual_element_is_hard_reject_even_with_high_priority():
    profile = _profile(
        strategy_id="element_profile",
        priority=999,
        introduced_visual_elements=["visual_element_alpha"],
        visual_element_evidence_requirements=(_element_requirement(),),
    )
    registry = _registry(profile, _fallback_profile())

    decision = resolve_visual_strategy(
        _context(),
        _intent(prohibited_visual_elements=["visual_element_alpha"]),
        registry,
    )

    assert decision.strategy_id == "fallback_profile"
    rejected = next(item for item in decision.trace.candidates if item.strategy_id == "element_profile")
    assert VisualStrategyRejectionCode.PROHIBITED_VISUAL_ELEMENT in rejected.rejection_codes


def test_visual_element_evidence_requires_correct_source():
    element_requirement = VisualElementEvidenceRequirement(
        element="visual_element_alpha",
        requirements=(
            VisualStrategyTagRequirement(
                source=VisualStrategyContextSource.PRODUCT_VISUAL_FACT,
                all_of=["product_signal_beta"],
            ),
        ),
    )
    profile = _profile(
        strategy_id="element_profile",
        introduced_visual_elements=["visual_element_alpha"],
        visual_element_evidence_requirements=(element_requirement,),
    )
    registry = _registry(profile, _fallback_profile())

    business_only = resolve_visual_strategy(_context(business_tags=["product_signal_beta"]), _intent(), registry)
    product_visual = resolve_visual_strategy(_context(product_tags=["product_signal_beta"]), _intent(), registry)

    assert business_only.strategy_id == "fallback_profile"
    assert product_visual.strategy_id == "element_profile"


@pytest.mark.parametrize(
    "profile_kwargs,runtime,code",
    [
        ({"supported_domains": [CanonicalBusinessDomain.BEAUTY]}, VisualStrategyRuntimeContext(), VisualStrategyRejectionCode.UNSUPPORTED_DOMAIN),
        ({"supported_placements": ["instagram_feed"]}, VisualStrategyRuntimeContext(), VisualStrategyRejectionCode.PLACEMENT_MISMATCH),
        ({"supported_campaign_roles": ["role_alpha"]}, VisualStrategyRuntimeContext(), VisualStrategyRejectionCode.CAMPAIGN_ROLE_MISMATCH),
        ({"provider_capabilities": ["capability_alpha"]}, VisualStrategyRuntimeContext(), VisualStrategyRejectionCode.MISSING_PROVIDER_CAPABILITY),
    ],
)
def test_capability_filters_reject_profiles(profile_kwargs, runtime, code):
    profile = _profile(strategy_id="restricted_profile", **profile_kwargs)
    registry = _registry(profile, _fallback_profile())

    decision = resolve_visual_strategy(_context(), _intent(), registry, runtime=runtime)

    trace = next(item for item in decision.trace.candidates if item.strategy_id == "restricted_profile")
    assert code in trace.rejection_codes


def test_runtime_capabilities_roles_and_placement_make_profile_eligible():
    profile = _profile(
        strategy_id="restricted_profile",
        provider_capabilities=["capability_alpha"],
        supported_campaign_roles=["role_alpha"],
        supported_placements=["poster"],
    )
    registry = _registry(profile, _fallback_profile())

    decision = resolve_visual_strategy(
        _context(),
        _intent(),
        registry,
        runtime=VisualStrategyRuntimeContext(
            available_provider_capabilities=["capability_alpha"],
            campaign_roles=["role_alpha"],
            placement="poster",
        ),
    )

    assert decision.strategy_id == "restricted_profile"


def test_runtime_placement_conflict_with_ad_format_is_typed_error():
    registry = _registry(_profile())

    resolve_visual_strategy(_context(placement="poster"), _intent(), registry, runtime=VisualStrategyRuntimeContext(placement="poster"))
    resolve_visual_strategy(_context(placement="poster"), _intent(), registry, runtime=VisualStrategyRuntimeContext())
    with pytest.raises(VisualStrategyRuntimeContextConflictError):
        resolve_visual_strategy(
            _context(placement="poster"),
            _intent(),
            registry,
            runtime=VisualStrategyRuntimeContext(placement="instagram_feed"),
        )


def test_required_excluded_and_preferred_tag_semantics():
    required = _profile(strategy_id="required_profile", required_tags=["required_alpha"])
    excluded = _profile(strategy_id="excluded_profile", excluded_tags=["business_signal_alpha"], priority=99)
    preferred = _profile(strategy_id="preferred_profile", preferred_tags=["preferred_alpha"], priority=50)
    registry = _registry(required, excluded, preferred, _fallback_profile())

    decision = resolve_visual_strategy(_context(business_tags=["business_signal_alpha"]), _intent(), registry)

    assert decision.strategy_id == "preferred_profile"
    required_trace = next(item for item in decision.trace.candidates if item.strategy_id == "required_profile")
    excluded_trace = next(item for item in decision.trace.candidates if item.strategy_id == "excluded_profile")
    preferred_trace = next(item for item in decision.trace.candidates if item.strategy_id == "preferred_profile")
    assert VisualStrategyRejectionCode.MISSING_REQUIRED_TAG in required_trace.rejection_codes
    assert VisualStrategyRejectionCode.EXCLUDED_TAG_PRESENT in excluded_trace.rejection_codes
    assert preferred_trace.eligible is True


def test_casefold_exact_matching_without_substring():
    profile = _profile(strategy_id="required_profile", required_tags=["alpha"])
    registry = _registry(profile, _fallback_profile())

    substring_decision = resolve_visual_strategy(_context(product_tags=["alphabet"]), _intent(), registry)
    casefold_decision = resolve_visual_strategy(_context(product_tags=["ALPHA"]), _intent(), registry)

    assert substring_decision.strategy_id == "fallback_profile"
    assert casefold_decision.strategy_id == "required_profile"


def test_score_axes_change_with_corresponding_signal_sources():
    product_profile = _profile(strategy_id="product_profile", preferred_tags=["product_signal_beta"])
    business_profile = _profile(strategy_id="business_profile", preferred_tags=["business_signal_alpha"])
    registry = _registry(product_profile, business_profile)

    product_decision = resolve_visual_strategy(_context(product_tags=["product_signal_beta"]), _intent(), registry)
    business_decision = resolve_visual_strategy(_context(business_tags=["business_signal_alpha"]), _intent(), registry)

    assert product_decision.trace.candidates[0].score is not None
    product_trace = next(item for item in product_decision.trace.candidates if item.strategy_id == "product_profile")
    business_trace = next(item for item in business_decision.trace.candidates if item.strategy_id == "business_profile")
    assert product_trace.score.product_relevance > product_trace.score.environment_fit
    assert business_trace.score.environment_fit > business_trace.score.product_relevance


def test_campaign_and_format_fit_axes_are_independent():
    profile = _profile(
        strategy_id="restricted_profile",
        supported_campaign_roles=["role_alpha"],
        supported_placements=["poster"],
    )
    registry = _registry(profile)

    decision = resolve_visual_strategy(
        _context(placement="poster"),
        _intent(),
        registry,
        runtime=VisualStrategyRuntimeContext(campaign_roles=["role_alpha"], placement="poster"),
    )

    assert decision.score.campaign_fit == 1.0
    assert decision.score.format_fit == 1.0


def test_fallback_penalty_and_total_score_formula_are_applied():
    fallback = _fallback_profile(fallback_tier=2)
    registry = _registry(fallback)

    decision = resolve_visual_strategy(_context(), _intent(), registry)

    assert decision.score.fallback_penalty == 0.4
    assert decision.score.total_score < 0.5


def test_unbacked_introduced_element_is_hard_reject_not_penalty_selection():
    fallback_profile = _fallback_profile(introduced_visual_elements=["visual_element_alpha"])
    registry = _registry(fallback_profile)

    with pytest.raises(NoEligibleVisualStrategyError) as exc:
        resolve_visual_strategy(_context(), _intent(), registry)

    trace = exc.value.trace.candidates[0]
    assert VisualStrategyRejectionCode.MISSING_VISUAL_ELEMENT_EVIDENCE in trace.rejection_codes
    assert trace.score is None


def test_reference_only_changes_reference_fit_not_hard_eligibility():
    profile = _profile(strategy_id="reference_profile", preferred_tags=["reference_signal_alpha"])
    registry = _registry(profile)

    without_reference = resolve_visual_strategy(_context(), _intent(), registry)
    with_reference = resolve_visual_strategy(
        _context(),
        _intent(),
        registry,
    )
    context_with_reference = _context()
    context_with_reference = context_with_reference.model_copy(update={"reference_style_profile": {"style": ["reference_signal_alpha"]}})
    with_reference = resolve_visual_strategy(context_with_reference, _intent(), registry)

    assert with_reference.score.reference_fit > without_reference.score.reference_fit


def test_fallback_selected_only_when_non_fallback_profiles_are_not_eligible():
    regular = _profile(strategy_id="regular_profile", priority=1)
    fallback = _fallback_profile(priority=999)
    registry = _registry(regular, fallback)

    decision = resolve_visual_strategy(_context(), _intent(), registry)

    assert decision.strategy_id == "regular_profile"
    assert decision.fallback_used is False


def test_no_eligible_strategy_raises_with_sanitized_trace():
    registry = _registry(_profile(strategy_id="blocked_profile", supported_domains=[CanonicalBusinessDomain.BEAUTY]))

    with pytest.raises(NoEligibleVisualStrategyError) as exc:
        resolve_visual_strategy(_context(), _intent(), registry)

    assert exc.value.trace.selected_strategy_id is None
    assert exc.value.trace.eligible_count == 0


def test_tie_break_uses_score_then_priority_then_strategy_id_deterministically():
    low = _profile(strategy_id="b_profile", priority=1)
    high = _profile(strategy_id="a_profile", priority=1)
    registry_a = _registry(low, high)
    registry_b = _registry(high, low)

    decision_a = resolve_visual_strategy(_context(), _intent(), registry_a)
    decision_b = resolve_visual_strategy(_context(), _intent(), registry_b)

    assert decision_a.strategy_id == "a_profile"
    assert decision_b.strategy_id == "a_profile"


def test_tie_break_prefers_total_score_then_evidence_then_product_then_priority():
    evidence_req = VisualStrategyTagRequirement(source=VisualStrategyContextSource.PRODUCT_VISUAL_FACT, all_of=["product_signal_beta"])
    evidence_high = _profile(strategy_id="evidence_high", required_tag_requirements=(evidence_req,), priority=1)
    total_high = _profile(strategy_id="total_high", preferred_tags=["reference_signal_alpha"], priority=1)
    product_high = _profile(strategy_id="product_high", required_tags=["product_signal_beta"], priority=1)
    priority_high = _profile(strategy_id="priority_high", priority=99)

    reference_context = _context(business_tags=["reference_signal_alpha"])
    reference_context = reference_context.model_copy(update={"reference_style_profile": {"style": ["reference_signal_alpha"]}})
    total_decision = resolve_visual_strategy(reference_context, _intent(), _registry(total_high, priority_high))
    evidence_decision = resolve_visual_strategy(_context(product_tags=["product_signal_beta"]), _intent(), _registry(evidence_high, total_high))
    product_decision = resolve_visual_strategy(_context(product_tags=["product_signal_beta"]), _intent(), _registry(product_high, priority_high))
    priority_decision = resolve_visual_strategy(_context(), _intent(), _registry(priority_high, _profile(strategy_id="priority_low", priority=1)))

    assert total_decision.strategy_id == "total_high"
    assert evidence_decision.strategy_id == "evidence_high"
    assert product_decision.strategy_id == "product_high"
    assert priority_decision.strategy_id == "priority_high"


def test_signal_snapshot_keeps_sources_separate_and_collects_reference_leaf_strings():
    context = _context(business_tags=["shared_signal"], product_tags=["shared_signal"])
    context = context.model_copy(update={"reference_style_profile": {"tokens": ["reference_signal_alpha"], "ignored": 1}})
    snapshot = build_visual_strategy_signal_snapshot(context, _intent())

    assert "shared_signal" in snapshot.business_signals
    assert "shared_signal" in snapshot.product_visual_signals
    assert "reference_signal_alpha" in snapshot.reference_style_signals


def test_product_visual_inference_does_not_satisfy_fact_requirement():
    profile = _profile(
        strategy_id="fact_required_profile",
        required_tag_requirements=(
            VisualStrategyTagRequirement(
                source=VisualStrategyContextSource.PRODUCT_VISUAL_FACT,
                all_of=["product_signal_beta"],
            ),
        ),
    )
    registry = _registry(profile, _fallback_profile())

    inference_only = resolve_visual_strategy(
        _context(permissible_inferences=["product_signal_beta"]),
        _intent(),
        registry,
    )
    fact_present = resolve_visual_strategy(
        _context(product_tags=["product_signal_beta"]),
        _intent(),
        registry,
    )

    assert inference_only.strategy_id == "fallback_profile"
    assert fact_present.strategy_id == "fact_required_profile"


def test_product_relevance_ignores_business_and_style_scoped_tokens():
    profile = _profile(
        strategy_id="mixed_scope_profile",
        preferred_tags=["style_signal_alpha"],
        required_tag_requirements=(
            VisualStrategyTagRequirement(source=VisualStrategyContextSource.BUSINESS, all_of=["business_signal_alpha"]),
            VisualStrategyTagRequirement(source=VisualStrategyContextSource.SEMANTIC_STYLE, all_of=["style_signal_alpha"]),
            VisualStrategyTagRequirement(source=VisualStrategyContextSource.PRODUCT_VISUAL_FACT, all_of=["product_signal_beta"]),
        ),
    )
    registry = _registry(profile, _fallback_profile())

    decision = resolve_visual_strategy(
        _context(business_tags=["business_signal_alpha"], product_tags=["product_signal_beta"]),
        _intent(desired_moods=["style_signal_alpha"]),
        registry,
    )

    trace = next(item for item in decision.trace.candidates if item.strategy_id == "mixed_scope_profile")
    assert trace.score.product_relevance == 1.0


def test_default_registry_bbq_business_only_product_only_and_combined_evidence():
    registry = build_default_visual_strategy_registry()

    business_only = resolve_visual_strategy(
        _context(canonical_domain=CanonicalBusinessDomain.FOOD_AND_BEVERAGE, business_tags=["korean_bbq"]),
        _intent(),
        registry,
    )
    product_only = resolve_visual_strategy(
        _context(
            canonical_domain=CanonicalBusinessDomain.FOOD_AND_BEVERAGE,
            product_tags=["grilled_meat"],
            preparation_methods=["table_grilled"],
            permissible_inferences=["smoke"],
        ),
        _intent(),
        registry,
    )
    combined = resolve_visual_strategy(
        _context(
            canonical_domain=CanonicalBusinessDomain.FOOD_AND_BEVERAGE,
            business_tags=["korean_bbq"],
            product_tags=["grilled_meat"],
            preparation_methods=["table_grilled"],
            permissible_inferences=["smoke"],
        ),
        _intent(),
        registry,
    )

    assert business_only.strategy_id == "generic_clean_ad_background"
    assert product_only.strategy_id == "generic_clean_ad_background"
    assert combined.strategy_id == "restaurant_bbq_warm_grill"


def test_default_registry_bbq_rejects_non_matching_product_with_prohibitions():
    registry = build_default_visual_strategy_registry()

    decision = resolve_visual_strategy(
        _context(
            canonical_domain=CanonicalBusinessDomain.FOOD_AND_BEVERAGE,
            business_tags=["korean_bbq"],
            product_tags=["fried_potato"],
            preparation_methods=["fried"],
            prohibited_inferences=["grill", "smoke", "meat"],
        ),
        _intent(),
        registry,
    )

    assert decision.strategy_id == "generic_clean_ad_background"
    bbq_trace = next(item for item in decision.trace.candidates if item.strategy_id == "restaurant_bbq_warm_grill")
    assert VisualStrategyRejectionCode.PROHIBITED_VISUAL_ELEMENT in bbq_trace.rejection_codes
