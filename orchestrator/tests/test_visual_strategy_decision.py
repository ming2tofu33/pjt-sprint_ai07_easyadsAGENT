from __future__ import annotations

import pytest
from pydantic import ValidationError

from orchestrator.app.llm.ad_format_presets import build_ad_format_spec
from orchestrator.app.llm.domain_routing import CanonicalBusinessDomain, DomainRoutingResult, DomainSupportStatus
from orchestrator.app.llm.visual_strategy_decision import (
    VISUAL_STRATEGY_ROUTE_VERSION,
    VisualStrategyDecisionMaterializationError,
    build_visual_strategy_decision,
    validate_decision_against_profile,
)
from orchestrator.app.llm.visual_strategy_resolver import resolve_visual_strategy
from orchestrator.app.llm.visual_strategy_registry import VisualStrategyRegistry
from orchestrator.app.schemas.business_context import BusinessEnvironmentContext
from orchestrator.app.schemas.campaign_context import CampaignContext
from orchestrator.app.schemas.creative_routing import CreativeRoutingContext
from orchestrator.app.schemas.input_evidence import EvidenceItem
from orchestrator.app.schemas.product_understanding import ProductUnderstanding
from orchestrator.app.schemas.product_visual_context import ProductVisualContext
from orchestrator.app.schemas.visual_semantic_intent import (
    SemanticIntentAttribution,
    VisualSemanticIntent,
    VisualSemanticIntentGenerationResult,
)
from orchestrator.app.schemas.visual_strategy import (
    VisualElementEvidenceRequirement,
    VisualStrategyContextSource,
    VisualStrategyProfile,
    VisualStrategyResourceCatalog,
    VisualStrategyTagRequirement,
)
from orchestrator.app.schemas.visual_strategy_resolution import VisualStrategyDecision, VisualStrategyFallbackReason


def _resources() -> VisualStrategyResourceCatalog:
    return VisualStrategyResourceCatalog(
        composition_template_ids=["template_alpha", "template_beta"],
        mood_preset_ids=["preset_alpha", "preset_beta"],
        copy_tone_profile_ids=["tone_alpha", "tone_beta"],
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


def _context(**overrides) -> CreativeRoutingContext:
    product_fact = EvidenceItem(
        evidence_id="product:e1",
        key="fact",
        value="product_signal_alpha",
        source="user_text",
        evidence_class="verified_fact",
        confidence=0.8,
        usable_for_copy=True,
    )
    data = {
        "domain": DomainRoutingResult(
            raw_business_type="retail",
            canonical_domain=CanonicalBusinessDomain.RETAIL,
            support_status=DomainSupportStatus.SPECIALIZED,
            evidence_refs=["domain:e1"],
            confidence=0.9,
        ),
        "business": BusinessEnvironmentContext(
            broad_domain=CanonicalBusinessDomain.RETAIL,
            business_tags=["business_signal_alpha"],
            evidence_refs=["business:e1", "business:e1"],
            confidence=0.7,
        ),
        "product": ProductUnderstanding(
            product_name="synthetic product",
            broad_category="home_and_living",
            category_path=["home_and_living", "synthetic_product"],
            normalized_product_type="synthetic_product",
            verified_facts=[product_fact],
            confidence=0.8,
        ),
        "product_visual": ProductVisualContext(
            product_name="synthetic product",
            category_path=["home_and_living", "synthetic_product"],
            product_tags=["product_signal_beta"],
            visible_attributes=["subject_attribute_beta"],
            explicit_preparation_methods=["preparation_gamma"],
            prohibited_visual_inferences=["NoSmoke", "duplicate"],
            evidence_refs=["product_visual:e1"],
            confidence=0.75,
        ),
        "campaign": CampaignContext(confidence=0.0),
        "ad_format": build_ad_format_spec("poster"),
        "resolver_version": "resolver-test",
    }
    data.update(overrides)
    return CreativeRoutingContext(**data)


def _intent(**overrides) -> VisualSemanticIntent:
    data = {
        "subject_priority": 0.8,
        "environment_priority": 0.7,
        "text_priority": 0.5,
        "required_visual_facts": ["subject_fact_alpha"],
        "desired_moods": ["mood_delta"],
        "lighting_preferences": ["lighting_epsilon"],
        "prohibited_visual_elements": ["nosmoke", "semantic_negative"],
        "copy_presence_mode": "copy_optional",
        "confidence": 0.85,
    }
    data.update(overrides)
    return VisualSemanticIntent(**data)


def _intent_result(intent: VisualSemanticIntent) -> VisualSemanticIntentGenerationResult:
    return VisualSemanticIntentGenerationResult(
        intent=intent,
        attributions=[
            SemanticIntentAttribution(
                field_name="required_visual_facts",
                item_value="subject_fact_alpha",
                evidence_refs=["semantic:e1"],
                source_paths=["$.intent.required_visual_facts[0]"],
                is_derived=False,
            )
        ],
        ambiguity_flags=[],
        input_projection_hash="hash",
    )


def test_decision_materializes_guidance_constraints_and_copy_presence():
    requirement = VisualElementEvidenceRequirement(
        element="visual_element_alpha",
        requirements=(VisualStrategyTagRequirement(source=VisualStrategyContextSource.PRODUCT_VISUAL_FACT, all_of=["product_signal_beta"]),),
    )
    profile = _profile(
        introduced_visual_elements=["visual_element_alpha"],
        visual_element_evidence_requirements=(requirement,),
    )
    registry = _registry(profile)
    intent = _intent()

    decision = resolve_visual_strategy(_context(), intent, registry)

    assert decision.route_version == VISUAL_STRATEGY_ROUTE_VERSION
    assert decision.copy_presence_mode == "copy_optional"
    assert decision.subject_guidance == (
        "subject_fact_alpha",
        "subject_attribute_beta",
        "preparation_gamma",
        "visual_element_alpha",
    )
    assert decision.environment_guidance == ("mood_delta", "lighting_epsilon")
    assert decision.negative_constraints == ("NoSmoke", "duplicate", "semantic_negative")


def test_decision_uses_single_selected_profile_resource_bundle():
    profile_a = _profile(strategy_id="profile_a", composition_template_id="template_alpha", mood_preset_id="preset_alpha", copy_tone_profile_id="tone_alpha")
    profile_b = _profile(strategy_id="profile_b", composition_template_id="template_beta", mood_preset_id="preset_beta", copy_tone_profile_id="tone_beta", priority=1)

    decision = resolve_visual_strategy(_context(), _intent(), _registry(profile_a, profile_b))

    assert (decision.composition_template_id, decision.mood_preset_id, decision.copy_tone_profile_id) == (
        "template_alpha",
        "preset_alpha",
        "tone_alpha",
    )
    validate_decision_against_profile(decision, profile_a)


def test_evidence_refs_use_selected_requirement_sources_without_invention():
    profile = _profile(
        required_tag_requirements=(
            VisualStrategyTagRequirement(source=VisualStrategyContextSource.BUSINESS, all_of=["business_signal_alpha"]),
            VisualStrategyTagRequirement(source=VisualStrategyContextSource.PRODUCT, any_of=["product_signal_alpha"]),
            VisualStrategyTagRequirement(source=VisualStrategyContextSource.PRODUCT_VISUAL_FACT, all_of=["product_signal_beta"]),
            VisualStrategyTagRequirement(source=VisualStrategyContextSource.SEMANTIC_FACT, all_of=["subject_fact_alpha"]),
        )
    )
    registry = _registry(profile)
    intent = _intent()

    decision = resolve_visual_strategy(
        _context(),
        intent,
        registry,
    )
    selected = next(candidate for candidate in decision.trace.candidates if candidate.strategy_id == decision.strategy_id)
    rebuilt = build_visual_strategy_decision(
        context=_context(),
        intent=intent,
        selected_profile=profile,
        selected_trace=selected,
        resolution_trace=decision.trace,
        registry=registry,
        intent_generation_result=_intent_result(intent),
    )

    assert rebuilt.evidence_refs == ("domain:e1", "business:e1", "product:e1", "product_visual:e1", "semantic:e1")


def test_evidence_refs_do_not_force_business_or_semantic_refs_without_requirements():
    decision = resolve_visual_strategy(_context(), _intent(), _registry(_profile()))

    assert decision.evidence_refs == ("domain:e1",)


def test_confidence_uses_input_min_evidence_alignment_and_fallback_multiplier():
    primary = _profile(required_tags=["missing"])
    fallback = _profile(strategy_id="fallback_profile", fallback_tier=1, priority=1)
    registry = _registry(primary, fallback)

    decision = resolve_visual_strategy(_context(), _intent(), registry)

    assert decision.fallback_used is True
    assert decision.fallback_reason == VisualStrategyFallbackReason.NO_ELIGIBLE_PRIMARY_STRATEGY
    assert decision.confidence == 0.525
    assert decision.score.total_score != decision.confidence


def test_empty_campaign_confidence_does_not_zero_decision_confidence():
    decision = resolve_visual_strategy(_context(), _intent(), _registry(_profile()))

    assert decision.confidence > 0


def test_fallback_reason_invariant():
    decision = resolve_visual_strategy(_context(), _intent(), _registry(_profile()))
    payload = decision.model_dump()

    assert decision.fallback_used is False
    assert decision.fallback_reason is None
    with pytest.raises(ValidationError):
        VisualStrategyDecision(**{**payload, "fallback_used": True, "fallback_tier": 1, "fallback_reason": None})
    with pytest.raises(ValidationError):
        VisualStrategyDecision(**{**payload, "fallback_reason": VisualStrategyFallbackReason.NO_ELIGIBLE_PRIMARY_STRATEGY})


def test_intent_generation_result_must_match_intent():
    profile = _profile()
    registry = _registry(profile)
    intent = _intent()
    decision = resolve_visual_strategy(_context(), intent, registry)
    selected = next(candidate for candidate in decision.trace.candidates if candidate.strategy_id == decision.strategy_id)

    with pytest.raises(VisualStrategyDecisionMaterializationError):
        build_visual_strategy_decision(
            context=_context(),
            intent=intent,
            selected_profile=profile,
            selected_trace=selected,
            resolution_trace=decision.trace,
            registry=registry,
            intent_generation_result=_intent_result(_intent(copy_presence_mode="different")),
        )
