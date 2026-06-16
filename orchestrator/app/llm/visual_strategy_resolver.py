"""Deterministic resolver for visual strategy profiles."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any

from orchestrator.app.llm.visual_strategy_decision import build_visual_strategy_decision
from orchestrator.app.llm.visual_strategy_registry import VisualStrategyRegistry
from orchestrator.app.schemas.creative_routing import CreativeRoutingContext
from orchestrator.app.schemas.visual_semantic_intent import VisualSemanticIntent
from orchestrator.app.schemas.visual_semantic_intent import VisualSemanticIntentGenerationResult
from orchestrator.app.schemas.visual_strategy import (
    VisualElementEvidenceRequirement,
    VisualStrategyContextSource,
    VisualStrategyProfile,
    VisualStrategyTagRequirement,
)
from orchestrator.app.schemas.visual_strategy_resolution import (
    VisualStrategyCandidateTrace,
    VisualStrategyDecisionConfidencePolicy,
    VisualStrategyDecision,
    VisualStrategyFallbackReason,
    VisualStrategyRejectionCode,
    VisualStrategyResolutionTrace,
    VisualStrategyRuntimeContext,
    VisualStrategyScore,
    VisualStrategyScoringPolicy,
    VisualStrategySignalSnapshot,
)


RESOLVER_VERSION = "visual-strategy-resolver-v2"


class NoEligibleVisualStrategyError(Exception):
    def __init__(self, trace: VisualStrategyResolutionTrace) -> None:
        super().__init__("no eligible visual strategy")
        self.trace = trace


class VisualStrategyRuntimeContextConflictError(ValueError):
    pass


@dataclass(frozen=True)
class _Candidate:
    profile: VisualStrategyProfile
    trace: VisualStrategyCandidateTrace


def build_default_visual_strategy_scoring_policy() -> VisualStrategyScoringPolicy:
    return VisualStrategyScoringPolicy(
        version="visual-strategy-scoring-v1",
        evidence_alignment_weight=1.0,
        product_relevance_weight=1.0,
        campaign_fit_weight=0.5,
        format_fit_weight=0.5,
        environment_fit_weight=0.75,
        reference_fit_weight=0.25,
        unsupported_inference_penalty_weight=0.25,
        fallback_penalty_weight=0.35,
        unrestricted_axis_score=0.5,
        fallback_tier_step=0.2,
    )


def resolve_visual_strategy(
    context: CreativeRoutingContext,
    intent: VisualSemanticIntent,
    registry: VisualStrategyRegistry,
    *,
    runtime: VisualStrategyRuntimeContext | None = None,
    policy: VisualStrategyScoringPolicy | None = None,
    intent_generation_result: VisualSemanticIntentGenerationResult | None = None,
    decision_confidence_policy: VisualStrategyDecisionConfidencePolicy | None = None,
) -> VisualStrategyDecision:
    runtime_context = runtime or VisualStrategyRuntimeContext()
    scoring_policy = policy or build_default_visual_strategy_scoring_policy()
    snapshot = build_visual_strategy_signal_snapshot(context, intent, runtime=runtime_context)
    candidates = tuple(
        _evaluate_profile(profile, context, snapshot, scoring_policy, intent_generation_result)
        for profile in registry.list_profiles(include_disabled=True)
    )
    eligible = tuple(candidate for candidate in candidates if candidate.trace.eligible)
    eligible_non_fallback = tuple(candidate for candidate in eligible if candidate.profile.fallback_tier == 0)
    eligible_fallback = tuple(candidate for candidate in eligible if candidate.profile.fallback_tier > 0)
    enabled_primary = tuple(candidate for candidate in candidates if candidate.profile.enabled and candidate.profile.fallback_tier == 0)
    domain_supported_primary_count = sum(1 for candidate in enabled_primary if context.domain.canonical_domain in candidate.profile.supported_domains)
    unsupported_domain = domain_supported_primary_count == 0
    missing_specialized_profile = domain_supported_primary_count > 0 and not eligible_non_fallback
    fallback_reason = _fallback_reason(
        fallback_used=not bool(eligible_non_fallback),
        unsupported_domain=unsupported_domain,
        missing_specialized_profile=missing_specialized_profile,
    )
    selectable = eligible_non_fallback or eligible_fallback

    if not selectable:
        trace = _build_trace(
            registry=registry,
            policy=scoring_policy,
            candidates=tuple(candidate.trace for candidate in candidates),
            selected=None,
            fallback_used=False,
            domain_supported_primary_count=domain_supported_primary_count,
            fallback_reason=None,
            unsupported_domain=unsupported_domain,
            missing_specialized_profile=missing_specialized_profile,
        )
        raise NoEligibleVisualStrategyError(trace)

    selected = sorted(
        selectable,
        key=lambda candidate: (
            -candidate.trace.score.total_score if candidate.trace.score else 0.0,
            -candidate.trace.score.evidence_alignment if candidate.trace.score else 0.0,
            -candidate.trace.score.product_relevance if candidate.trace.score else 0.0,
            -candidate.profile.priority,
            candidate.profile.strategy_id,
        ),
    )[0]
    fallback_used = selected.profile.fallback_tier > 0
    trace = _build_trace(
        registry=registry,
        policy=scoring_policy,
        candidates=tuple(candidate.trace for candidate in candidates),
        selected=selected,
        fallback_used=fallback_used,
        domain_supported_primary_count=domain_supported_primary_count,
        fallback_reason=fallback_reason if fallback_used else None,
        unsupported_domain=unsupported_domain if fallback_used else False,
        missing_specialized_profile=missing_specialized_profile if fallback_used else False,
    )
    return build_visual_strategy_decision(
        context=context,
        intent=intent,
        selected_profile=selected.profile,
        selected_trace=selected.trace,
        resolution_trace=trace,
        registry=registry,
        intent_generation_result=intent_generation_result,
        confidence_policy=decision_confidence_policy,
    )


def build_visual_strategy_signal_snapshot(
    context: CreativeRoutingContext,
    intent: VisualSemanticIntent,
    *,
    runtime: VisualStrategyRuntimeContext | None = None,
) -> VisualStrategySignalSnapshot:
    runtime_context = runtime or VisualStrategyRuntimeContext()
    context_placement = _key(context.ad_format.ad_format)
    runtime_placement = _key(runtime_context.placement) if runtime_context.placement else None
    if runtime_placement is not None and runtime_placement != context_placement:
        raise VisualStrategyRuntimeContextConflictError("runtime placement conflicts with AdFormatSpec")
    placement = runtime_placement or context_placement
    business_signals = _normalized_set(
        [
            context.business.venue_type,
            context.business.service_model,
            *context.business.business_tags,
            *context.business.environment_tags,
        ]
    )
    product_signals = _normalized_set(
        [
            context.product.normalized_product_type,
            context.product.product_variant,
            context.product.product_form,
            *context.product.category_path,
            *(item.normalized_value or item.value for item in context.product.verified_facts),
        ]
    )
    product_visual_fact_signals = _normalized_set(
        [
            *context.product_visual.product_tags,
            *context.product_visual.visible_attributes,
            *context.product_visual.explicit_preparation_methods,
        ]
    )
    product_visual_inference_signals = _normalized_set(context.product_visual.permissible_visual_inferences)
    product_visual_signals = product_visual_fact_signals | product_visual_inference_signals
    semantic_fact_signals = _normalized_set(intent.required_visual_facts)
    semantic_style_signals = _normalized_set(
        [
            *intent.desired_moods,
            *intent.desired_materials,
            *intent.lighting_preferences,
            *intent.composition_preferences,
            intent.copy_presence_mode,
        ]
    )
    semantic_intent_signals = semantic_fact_signals | semantic_style_signals
    prohibited = _normalized_set([*context.product_visual.prohibited_visual_inferences, *intent.prohibited_visual_elements])
    reference_signals = _reference_style_signals(context.reference_style_profile)
    all_signals = business_signals | product_signals | product_visual_signals | semantic_intent_signals
    return VisualStrategySignalSnapshot(
        business_signals=business_signals,
        product_signals=product_signals,
        product_visual_signals=product_visual_signals,
        product_visual_fact_signals=product_visual_fact_signals,
        product_visual_inference_signals=product_visual_inference_signals,
        semantic_intent_signals=semantic_intent_signals,
        semantic_fact_signals=semantic_fact_signals,
        semantic_style_signals=semantic_style_signals,
        all_signals=all_signals,
        prohibited_visual_elements=prohibited,
        campaign_roles=runtime_context.campaign_roles,
        placement=placement,
        available_provider_capabilities=runtime_context.available_provider_capabilities,
        reference_style_signals=reference_signals,
    )


def _evaluate_profile(
    profile: VisualStrategyProfile,
    context: CreativeRoutingContext,
    snapshot: VisualStrategySignalSnapshot,
    policy: VisualStrategyScoringPolicy,
    intent_generation_result: VisualSemanticIntentGenerationResult | None,
) -> _Candidate:
    rejection_codes: list[VisualStrategyRejectionCode] = []
    if not profile.enabled:
        rejection_codes.append(VisualStrategyRejectionCode.DISABLED)
    if context.domain.canonical_domain not in profile.supported_domains:
        rejection_codes.append(VisualStrategyRejectionCode.UNSUPPORTED_DOMAIN)
    if profile.provider_capabilities and not profile.provider_capabilities <= snapshot.available_provider_capabilities:
        rejection_codes.append(VisualStrategyRejectionCode.MISSING_PROVIDER_CAPABILITY)
    if profile.supported_placements and (snapshot.placement is None or _key(snapshot.placement) not in _key_set(profile.supported_placements)):
        rejection_codes.append(VisualStrategyRejectionCode.PLACEMENT_MISMATCH)
    if profile.supported_campaign_roles and not (_key_set(profile.supported_campaign_roles) & _key_set(snapshot.campaign_roles)):
        rejection_codes.append(VisualStrategyRejectionCode.CAMPAIGN_ROLE_MISMATCH)

    required = _key_set(profile.required_tags)
    preferred = _key_set(profile.preferred_tags)
    excluded = _key_set(profile.excluded_tags)
    matched_required = required & snapshot.all_signals
    missing_required = required - snapshot.all_signals
    matched_preferred = preferred & snapshot.all_signals
    matched_excluded = excluded & snapshot.all_signals
    if missing_required:
        rejection_codes.append(VisualStrategyRejectionCode.MISSING_REQUIRED_TAG)
    if matched_excluded:
        rejection_codes.append(VisualStrategyRejectionCode.EXCLUDED_TAG_PRESENT)

    matched_source, missing_source, source_evidence_refs = _evaluate_source_requirements(
        profile.required_tag_requirements,
        snapshot,
        context,
        intent_generation_result,
    )
    if missing_source:
        rejection_codes.append(VisualStrategyRejectionCode.MISSING_SOURCE_REQUIREMENT)

    introduced = _key_set(profile.introduced_visual_elements)
    blocked_elements = introduced & snapshot.prohibited_visual_elements
    if blocked_elements:
        rejection_codes.append(VisualStrategyRejectionCode.PROHIBITED_VISUAL_ELEMENT)

    matched_element_requirements, missing_element_requirements, element_evidence_refs = _evaluate_element_requirements(
        profile.visual_element_evidence_requirements,
        snapshot,
        context,
        intent_generation_result,
    )
    if missing_element_requirements:
        rejection_codes.append(VisualStrategyRejectionCode.MISSING_VISUAL_ELEMENT_EVIDENCE)
    evidence_backed_elements = frozenset(_key(item.element) for item in profile.visual_element_evidence_requirements)
    unsupported_elements = introduced - evidence_backed_elements - blocked_elements
    if unsupported_elements:
        rejection_codes.append(VisualStrategyRejectionCode.MISSING_VISUAL_ELEMENT_EVIDENCE)

    eligible = not rejection_codes
    score = (
        _score_profile(
            profile=profile,
            snapshot=snapshot,
            policy=policy,
            matched_source_count=len(matched_source) + len(matched_element_requirements),
            source_requirement_count=len(profile.required_tag_requirements) + len(profile.visual_element_evidence_requirements),
            unsupported_elements=unsupported_elements,
        )
        if eligible
        else None
    )
    trace = VisualStrategyCandidateTrace(
        strategy_id=profile.strategy_id,
        eligible=eligible,
        fallback_tier=profile.fallback_tier,
        fallback_role=profile.fallback_role,
        rejection_codes=tuple(dict.fromkeys(rejection_codes)),
        matched_required_tags=matched_required,
        missing_required_tags=missing_required,
        matched_preferred_tags=matched_preferred,
        matched_excluded_tags=matched_excluded,
        matched_source_requirements=tuple(sorted([*matched_source, *matched_element_requirements])),
        missing_source_requirements=tuple(sorted([*missing_source, *missing_element_requirements])),
        blocked_visual_elements=blocked_elements,
        unsupported_visual_elements=unsupported_elements,
        matched_evidence_refs=_stable_unique([*source_evidence_refs, *element_evidence_refs]),
        evidence_backed_visual_elements=evidence_backed_elements,
        score=score,
    )
    return _Candidate(profile=profile, trace=trace)


def _score_profile(
    *,
    profile: VisualStrategyProfile,
    snapshot: VisualStrategySignalSnapshot,
    policy: VisualStrategyScoringPolicy,
    matched_source_count: int,
    source_requirement_count: int,
    unsupported_elements: frozenset[str],
) -> VisualStrategyScore:
    unrestricted = policy.unrestricted_axis_score
    evidence_alignment = matched_source_count / source_requirement_count if source_requirement_count else unrestricted
    product_relevant_signals = snapshot.product_signals | snapshot.product_visual_fact_signals | snapshot.semantic_fact_signals
    product_targets = (
        _key_set(profile.required_tags)
        | _requirement_tokens_for_sources(
            profile.required_tag_requirements,
            {
                VisualStrategyContextSource.PRODUCT,
                VisualStrategyContextSource.PRODUCT_VISUAL,
                VisualStrategyContextSource.PRODUCT_VISUAL_FACT,
                VisualStrategyContextSource.SEMANTIC_FACT,
            },
        )
        | _element_requirement_tokens_for_sources(
            profile.visual_element_evidence_requirements,
            {
                VisualStrategyContextSource.PRODUCT,
                VisualStrategyContextSource.PRODUCT_VISUAL,
                VisualStrategyContextSource.PRODUCT_VISUAL_FACT,
                VisualStrategyContextSource.SEMANTIC_FACT,
            },
        )
    )
    product_relevance = _coverage(product_targets, product_relevant_signals, unrestricted)
    campaign_fit = 1.0 if profile.supported_campaign_roles and _key_set(profile.supported_campaign_roles) & _key_set(snapshot.campaign_roles) else unrestricted
    format_fit = 1.0 if profile.supported_placements and snapshot.placement and _key(snapshot.placement) in _key_set(profile.supported_placements) else unrestricted
    environment_fit = _coverage(_key_set(profile.preferred_tags), snapshot.business_signals, unrestricted)
    reference_fit = _coverage(_key_set(profile.preferred_tags), snapshot.reference_style_signals, unrestricted)
    introduced = _key_set(profile.introduced_visual_elements)
    unsupported_penalty = len(unsupported_elements) / len(introduced) if introduced else 0.0
    fallback_penalty = min(1.0, profile.fallback_tier * policy.fallback_tier_step)

    positive_weight_sum = (
        policy.evidence_alignment_weight
        + policy.product_relevance_weight
        + policy.campaign_fit_weight
        + policy.format_fit_weight
        + policy.environment_fit_weight
        + policy.reference_fit_weight
    )
    positive = (
        evidence_alignment * policy.evidence_alignment_weight
        + product_relevance * policy.product_relevance_weight
        + campaign_fit * policy.campaign_fit_weight
        + format_fit * policy.format_fit_weight
        + environment_fit * policy.environment_fit_weight
        + reference_fit * policy.reference_fit_weight
    ) / positive_weight_sum
    penalty = (
        unsupported_penalty * policy.unsupported_inference_penalty_weight
        + fallback_penalty * policy.fallback_penalty_weight
    )
    return VisualStrategyScore(
        evidence_alignment=round(_clamp(evidence_alignment), 6),
        product_relevance=round(_clamp(product_relevance), 6),
        campaign_fit=round(_clamp(campaign_fit), 6),
        format_fit=round(_clamp(format_fit), 6),
        environment_fit=round(_clamp(environment_fit), 6),
        reference_fit=round(_clamp(reference_fit), 6),
        unsupported_inference_penalty=round(_clamp(unsupported_penalty), 6),
        fallback_penalty=round(_clamp(fallback_penalty), 6),
        total_score=round(_clamp(positive - penalty), 6),
    )


def _build_trace(
    *,
    registry: VisualStrategyRegistry,
    policy: VisualStrategyScoringPolicy,
    candidates: tuple[VisualStrategyCandidateTrace, ...],
    selected: _Candidate | None,
    fallback_used: bool,
    domain_supported_primary_count: int,
    fallback_reason: VisualStrategyFallbackReason | None,
    unsupported_domain: bool,
    missing_specialized_profile: bool,
) -> VisualStrategyResolutionTrace:
    eligible_count = sum(1 for candidate in candidates if candidate.eligible)
    eligible_primary_count = sum(1 for candidate in candidates if candidate.eligible and candidate.fallback_tier == 0)
    eligible_fallback_count = sum(1 for candidate in candidates if candidate.eligible and candidate.fallback_tier > 0)
    return VisualStrategyResolutionTrace(
        resolver_version=RESOLVER_VERSION,
        scoring_policy_version=policy.version,
        registry_version=registry.version,
        registry_snapshot_hash=registry.snapshot_hash,
        candidate_count=len(candidates),
        eligible_count=eligible_count,
        domain_supported_primary_count=domain_supported_primary_count,
        eligible_primary_count=eligible_primary_count,
        eligible_fallback_count=eligible_fallback_count,
        non_fallback_eligible_count=eligible_primary_count,
        fallback_eligible_count=eligible_fallback_count,
        selected_strategy_id=selected.profile.strategy_id if selected else None,
        fallback_used=fallback_used,
        fallback_reason=fallback_reason,
        fallback_role=selected.profile.fallback_role if selected and fallback_used else None,
        unsupported_domain=unsupported_domain,
        missing_specialized_profile=missing_specialized_profile,
        candidates=candidates,
    )


def _fallback_reason(
    *,
    fallback_used: bool,
    unsupported_domain: bool,
    missing_specialized_profile: bool,
) -> VisualStrategyFallbackReason | None:
    if not fallback_used:
        return None
    if unsupported_domain:
        return VisualStrategyFallbackReason.UNSUPPORTED_DOMAIN
    if missing_specialized_profile:
        return VisualStrategyFallbackReason.MISSING_SPECIALIZED_PROFILE
    return VisualStrategyFallbackReason.MISSING_SPECIALIZED_PROFILE


def _evaluate_source_requirements(
    requirements: Iterable[VisualStrategyTagRequirement],
    snapshot: VisualStrategySignalSnapshot,
    context: CreativeRoutingContext,
    intent_generation_result: VisualSemanticIntentGenerationResult | None,
) -> tuple[list[str], list[str], list[str]]:
    matched: list[str] = []
    missing: list[str] = []
    evidence_refs: list[str] = []
    for index, requirement in enumerate(requirements):
        signals = _signals_for_source(requirement.source, snapshot)
        label = _requirement_label("source", index, requirement)
        if _requirement_matches(requirement, signals):
            matched.append(label)
            evidence_refs.extend(_evidence_refs_for_requirement(requirement, context, intent_generation_result))
        else:
            missing.append(label)
    return matched, missing, evidence_refs


def _evaluate_element_requirements(
    requirements: Iterable[VisualElementEvidenceRequirement],
    snapshot: VisualStrategySignalSnapshot,
    context: CreativeRoutingContext,
    intent_generation_result: VisualSemanticIntentGenerationResult | None,
) -> tuple[list[str], list[str], list[str]]:
    matched: list[str] = []
    missing: list[str] = []
    evidence_refs: list[str] = []
    for index, element_requirement in enumerate(requirements):
        label = f"element:{_key(element_requirement.element)}:{index}"
        if all(_requirement_matches(requirement, _signals_for_source(requirement.source, snapshot)) for requirement in element_requirement.requirements):
            matched.append(label)
            for requirement in element_requirement.requirements:
                evidence_refs.extend(_evidence_refs_for_requirement(requirement, context, intent_generation_result))
        else:
            missing.append(label)
    return matched, missing, evidence_refs


def _requirement_matches(requirement: VisualStrategyTagRequirement, signals: frozenset[str]) -> bool:
    all_of = _key_set(requirement.all_of)
    any_of = _key_set(requirement.any_of)
    return all_of <= signals and (not any_of or bool(any_of & signals))


def _evidence_refs_for_requirement(
    requirement: VisualStrategyTagRequirement,
    context: CreativeRoutingContext,
    intent_generation_result: VisualSemanticIntentGenerationResult | None,
) -> tuple[str, ...]:
    tokens = _key_set(requirement.all_of) | _key_set(requirement.any_of)
    if requirement.source == VisualStrategyContextSource.BUSINESS:
        return _stable_unique(context.business.evidence_refs)
    if requirement.source == VisualStrategyContextSource.PRODUCT:
        return _stable_unique(
            item.evidence_id
            for item in context.product.verified_facts
            if _key(item.normalized_value or item.value) in tokens
        )
    if requirement.source in {
        VisualStrategyContextSource.PRODUCT_VISUAL,
        VisualStrategyContextSource.PRODUCT_VISUAL_FACT,
        VisualStrategyContextSource.PRODUCT_VISUAL_INFERENCE,
    }:
        return _stable_unique(context.product_visual.evidence_refs)
    if requirement.source in {
        VisualStrategyContextSource.SEMANTIC_INTENT,
        VisualStrategyContextSource.SEMANTIC_FACT,
        VisualStrategyContextSource.SEMANTIC_STYLE,
    }:
        if intent_generation_result is None:
            return ()
        return _stable_unique(
            ref
            for attribution in intent_generation_result.attributions
            if attribution.item_value is not None and _key(attribution.item_value) in tokens
            for ref in attribution.evidence_refs
        )
    return ()


def _signals_for_source(source: VisualStrategyContextSource, snapshot: VisualStrategySignalSnapshot) -> frozenset[str]:
    return {
        VisualStrategyContextSource.BUSINESS: snapshot.business_signals,
        VisualStrategyContextSource.PRODUCT: snapshot.product_signals,
        VisualStrategyContextSource.PRODUCT_VISUAL: snapshot.product_visual_fact_signals,
        VisualStrategyContextSource.PRODUCT_VISUAL_FACT: snapshot.product_visual_fact_signals,
        VisualStrategyContextSource.PRODUCT_VISUAL_INFERENCE: snapshot.product_visual_inference_signals,
        VisualStrategyContextSource.SEMANTIC_INTENT: snapshot.semantic_intent_signals,
        VisualStrategyContextSource.SEMANTIC_FACT: snapshot.semantic_fact_signals,
        VisualStrategyContextSource.SEMANTIC_STYLE: snapshot.semantic_style_signals,
    }[source]


def _requirement_label(prefix: str, index: int, requirement: VisualStrategyTagRequirement) -> str:
    tokens = sorted(_key_set(requirement.all_of) | _key_set(requirement.any_of))
    return f"{prefix}:{requirement.source.value}:{index}:{','.join(tokens)}"


def _requirement_tokens(requirements: Iterable[VisualStrategyTagRequirement]) -> frozenset[str]:
    return frozenset(token for requirement in requirements for token in (_key_set(requirement.all_of) | _key_set(requirement.any_of)))


def _requirement_tokens_for_sources(
    requirements: Iterable[VisualStrategyTagRequirement],
    sources: set[VisualStrategyContextSource],
) -> frozenset[str]:
    return frozenset(
        token
        for requirement in requirements
        if requirement.source in sources
        for token in (_key_set(requirement.all_of) | _key_set(requirement.any_of))
    )


def _element_requirement_tokens(requirements: Iterable[VisualElementEvidenceRequirement]) -> frozenset[str]:
    return frozenset(token for requirement in requirements for token in _requirement_tokens(requirement.requirements))


def _element_requirement_tokens_for_sources(
    requirements: Iterable[VisualElementEvidenceRequirement],
    sources: set[VisualStrategyContextSource],
) -> frozenset[str]:
    return frozenset(
        token
        for element_requirement in requirements
        for token in _requirement_tokens_for_sources(element_requirement.requirements, sources)
    )


def _coverage(targets: frozenset[str], signals: frozenset[str], unrestricted: float) -> float:
    return len(targets & signals) / len(targets) if targets else unrestricted


def _normalized_set(values: Iterable[Any]) -> frozenset[str]:
    return frozenset(_key(value) for value in values if value is not None and _key(value))


def _stable_unique(values: Iterable[str]) -> tuple[str, ...]:
    output: list[str] = []
    seen: set[str] = set()
    for value in values:
        if not isinstance(value, str):
            continue
        item = value.strip()
        if not item or item in seen:
            continue
        output.append(item)
        seen.add(item)
    return tuple(output)


def _key_set(values: Iterable[str]) -> frozenset[str]:
    return frozenset(_key(value) for value in values if _key(value))


def _key(value: Any) -> str:
    return str(value).strip().casefold()


def _clamp(value: float) -> float:
    return max(0.0, min(1.0, value))


def _reference_style_signals(value: Any) -> frozenset[str]:
    output: set[str] = set()

    def visit(item: Any) -> None:
        if isinstance(item, str):
            normalized = _key(item)
            if normalized:
                output.add(normalized)
            return
        if isinstance(item, list):
            for child in item:
                visit(child)
            return
        if isinstance(item, dict):
            for child in item.values():
                visit(child)

    visit(value or {})
    return frozenset(output)
