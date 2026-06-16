"""Materialize unified visual strategy decisions from resolver selection."""

from __future__ import annotations

from collections.abc import Iterable

from orchestrator.app.llm.visual_strategy_registry import VisualStrategyRegistry
from orchestrator.app.schemas.creative_routing import CreativeRoutingContext
from orchestrator.app.schemas.visual_semantic_intent import (
    VisualSemanticIntent,
    VisualSemanticIntentGenerationResult,
)
from orchestrator.app.schemas.visual_strategy import (
    VisualStrategyContextSource,
    VisualStrategyProfile,
    VisualStrategyTagRequirement,
)
from orchestrator.app.schemas.visual_strategy_resolution import (
    VisualStrategyCandidateTrace,
    VisualStrategyDecision,
    VisualStrategyDecisionConfidencePolicy,
    VisualStrategyFallbackReason,
    VisualStrategyResolutionTrace,
)


VISUAL_STRATEGY_ROUTE_VERSION = "visual-strategy-route-v1"


class VisualStrategyDecisionMaterializationError(ValueError):
    pass


def build_default_visual_strategy_decision_confidence_policy() -> VisualStrategyDecisionConfidencePolicy:
    return VisualStrategyDecisionConfidencePolicy(
        version="visual-strategy-decision-confidence-v1",
        fallback_confidence_multiplier=0.75,
    )


def build_visual_strategy_decision(
    *,
    context: CreativeRoutingContext,
    intent: VisualSemanticIntent,
    selected_profile: VisualStrategyProfile,
    selected_trace: VisualStrategyCandidateTrace,
    resolution_trace: VisualStrategyResolutionTrace,
    registry: VisualStrategyRegistry,
    intent_generation_result: VisualSemanticIntentGenerationResult | None = None,
    confidence_policy: VisualStrategyDecisionConfidencePolicy | None = None,
) -> VisualStrategyDecision:
    if intent_generation_result is not None and intent_generation_result.intent != intent:
        raise VisualStrategyDecisionMaterializationError("intent_generation_result intent does not match intent")
    if selected_trace.strategy_id != selected_profile.strategy_id:
        raise VisualStrategyDecisionMaterializationError("selected trace does not match selected profile")
    if resolution_trace.selected_strategy_id != selected_profile.strategy_id:
        raise VisualStrategyDecisionMaterializationError("resolution trace does not match selected profile")
    selected_profile_id = selected_profile.strategy_id
    canonical_trace = next(
        (candidate for candidate in resolution_trace.candidates if _candidate_strategy_id(candidate) == selected_profile_id),
        None,
    )
    if canonical_trace is None or selected_trace != canonical_trace:
        raise VisualStrategyDecisionMaterializationError("selected trace does not match resolution trace")

    negative_constraints = build_negative_constraints(context=context, intent=intent)
    introduced = {_key(value) for value in selected_profile.introduced_visual_elements}
    negative_keys = {_key(value) for value in negative_constraints}
    if introduced & negative_keys:
        raise VisualStrategyDecisionMaterializationError("selected profile introduces a prohibited visual element")

    policy = confidence_policy or build_default_visual_strategy_decision_confidence_policy()
    fallback_used = selected_profile.fallback_tier > 0
    decision = VisualStrategyDecision(
        strategy_id=selected_profile.strategy_id,
        route_version=VISUAL_STRATEGY_ROUTE_VERSION,
        resolver_version=resolution_trace.resolver_version,
        archetype=selected_profile.archetype,
        composition_template_id=selected_profile.composition_template_id,
        mood_preset_id=selected_profile.mood_preset_id,
        copy_tone_profile_id=selected_profile.copy_tone_profile_id,
        copy_presence_mode=intent.copy_presence_mode,
        subject_guidance=build_subject_guidance(
            context=context,
            intent=intent,
            selected_profile=selected_profile,
            selected_trace=selected_trace,
        ),
        environment_guidance=build_environment_guidance(intent=intent),
        negative_constraints=negative_constraints,
        matched_rules=build_matched_rules(selected_trace),
        rejected_strategy_ids=tuple(candidate.strategy_id for candidate in resolution_trace.candidates if not candidate.eligible),
        eligible_not_selected_strategy_ids=tuple(
            candidate.strategy_id
            for candidate in resolution_trace.candidates
            if candidate.eligible and candidate.strategy_id != selected_profile.strategy_id
        ),
        evidence_refs=collect_visual_strategy_evidence_refs(
            selected_trace=selected_trace,
        ),
        confidence=calculate_visual_strategy_decision_confidence(
            context=context,
            intent=intent,
            selected_profile=selected_profile,
            selected_trace=selected_trace,
            fallback_used=fallback_used,
            policy=policy,
        ),
        provider_capabilities=selected_profile.provider_capabilities,
        score=selected_trace.score,
        fallback_used=fallback_used,
        fallback_tier=selected_profile.fallback_tier,
        fallback_reason=VisualStrategyFallbackReason.NO_ELIGIBLE_PRIMARY_STRATEGY if fallback_used else None,
        registry_version=registry.version,
        registry_snapshot_hash=registry.snapshot_hash,
        confidence_policy_version=policy.version,
        trace=resolution_trace,
    )
    validate_decision_against_profile(decision, selected_profile)
    return decision


def build_subject_guidance(
    *,
    context: CreativeRoutingContext,
    intent: VisualSemanticIntent,
    selected_profile: VisualStrategyProfile,
    selected_trace: VisualStrategyCandidateTrace,
) -> tuple[str, ...]:
    return _stable_unique(
        [
            *intent.required_visual_facts,
            *context.product_visual.visible_attributes,
            *context.product_visual.explicit_preparation_methods,
            *[
                element
                for element in selected_profile.introduced_visual_elements
                if _key(element) in selected_trace.evidence_backed_visual_elements
            ],
        ],
        casefold=True,
    )


def build_environment_guidance(*, intent: VisualSemanticIntent) -> tuple[str, ...]:
    return _stable_unique(
        [
            *intent.desired_moods,
            *intent.desired_materials,
            *intent.lighting_preferences,
            *intent.composition_preferences,
        ],
        casefold=True,
    )


def build_negative_constraints(
    *,
    context: CreativeRoutingContext,
    intent: VisualSemanticIntent,
) -> tuple[str, ...]:
    return _stable_unique(
        [
            *context.product_visual.prohibited_visual_inferences,
            *intent.prohibited_visual_elements,
        ],
        casefold=True,
    )


def build_matched_rules(selected_trace: VisualStrategyCandidateTrace) -> tuple[str, ...]:
    return tuple(
        sorted(
            set(selected_trace.matched_required_tags)
            | set(selected_trace.matched_preferred_tags)
            | set(selected_trace.matched_source_requirements)
        )
    )


def collect_visual_strategy_evidence_refs(*, selected_trace: VisualStrategyCandidateTrace) -> tuple[str, ...]:
    return _stable_unique(selected_trace.matched_evidence_refs, casefold=False)


def calculate_visual_strategy_decision_confidence(
    *,
    context: CreativeRoutingContext,
    intent: VisualSemanticIntent,
    selected_profile: VisualStrategyProfile,
    selected_trace: VisualStrategyCandidateTrace,
    fallback_used: bool,
    policy: VisualStrategyDecisionConfidencePolicy,
) -> float:
    confidences = [context.domain.confidence, context.product_visual.confidence, intent.confidence]
    sources = _requirement_sources(selected_profile)
    if VisualStrategyContextSource.BUSINESS in sources:
        confidences.append(context.business.confidence)
    if VisualStrategyContextSource.PRODUCT in sources:
        confidences.append(context.product.confidence)
    if selected_profile.supported_campaign_roles and _campaign_has_claims(context):
        confidences.append(context.campaign.confidence)
    input_confidence = min(confidences)
    has_requirements = bool(
        selected_profile.required_tag_requirements
        or selected_profile.visual_element_evidence_requirements
    )
    evidence_factor = selected_trace.score.evidence_alignment if has_requirements else 1.0
    fallback_factor = policy.fallback_confidence_multiplier if fallback_used else 1.0
    return round(_clamp(input_confidence * evidence_factor * fallback_factor), 6)


def validate_decision_against_profile(
    decision: VisualStrategyDecision,
    profile: VisualStrategyProfile,
) -> None:
    expected = {
        "strategy_id": profile.strategy_id,
        "archetype": profile.archetype,
        "composition_template_id": profile.composition_template_id,
        "mood_preset_id": profile.mood_preset_id,
        "copy_tone_profile_id": profile.copy_tone_profile_id,
        "provider_capabilities": profile.provider_capabilities,
        "fallback_tier": profile.fallback_tier,
    }
    for field_name, expected_value in expected.items():
        if getattr(decision, field_name) != expected_value:
            raise VisualStrategyDecisionMaterializationError(f"decision {field_name} does not match selected profile")


def _campaign_has_claims(context: CreativeRoutingContext) -> bool:
    return bool(
        context.campaign.campaign_intent
        or context.campaign.campaign_status
        or context.campaign.promotion_goal
        or context.campaign.desired_positioning
    )


def _requirement_sources(profile: VisualStrategyProfile) -> set[VisualStrategyContextSource]:
    requirements: list[VisualStrategyTagRequirement] = [*profile.required_tag_requirements]
    for element_requirement in profile.visual_element_evidence_requirements:
        requirements.extend(element_requirement.requirements)
    return {requirement.source for requirement in requirements}


def _candidate_strategy_id(candidate: VisualStrategyCandidateTrace) -> str:
    return candidate.strategy_id


def _stable_unique(values: Iterable[str | None], *, casefold: bool) -> tuple[str, ...]:
    output: list[str] = []
    seen: set[str] = set()
    for value in values:
        if value is None or not isinstance(value, str):
            continue
        item = value.strip()
        if not item:
            continue
        key = item.casefold() if casefold else item
        if key in seen:
            continue
        seen.add(key)
        output.append(item)
    return tuple(output)


def _key(value: str) -> str:
    return value.strip().casefold()


def _clamp(value: float) -> float:
    return max(0.0, min(1.0, value))
