"""Deterministic resolver for visual strategy profiles."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any

from orchestrator.app.llm.visual_strategy_registry import VisualStrategyRegistry
from orchestrator.app.schemas.creative_routing import CreativeRoutingContext
from orchestrator.app.schemas.visual_semantic_intent import VisualSemanticIntent
from orchestrator.app.schemas.visual_strategy import (
    VisualElementEvidenceRequirement,
    VisualStrategyContextSource,
    VisualStrategyProfile,
    VisualStrategyTagRequirement,
)
from orchestrator.app.schemas.visual_strategy_resolution import (
    VisualStrategyCandidateTrace,
    VisualStrategyDecision,
    VisualStrategyRejectionCode,
    VisualStrategyResolutionTrace,
    VisualStrategyRuntimeContext,
    VisualStrategyScore,
    VisualStrategyScoringPolicy,
    VisualStrategySignalSnapshot,
)


RESOLVER_VERSION = "visual-strategy-resolver-v1"


class NoEligibleVisualStrategyError(Exception):
    def __init__(self, trace: VisualStrategyResolutionTrace) -> None:
        super().__init__("no eligible visual strategy")
        self.trace = trace


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
) -> VisualStrategyDecision:
    runtime_context = runtime or VisualStrategyRuntimeContext()
    scoring_policy = policy or build_default_visual_strategy_scoring_policy()
    snapshot = build_visual_strategy_signal_snapshot(context, intent, runtime=runtime_context)
    candidates = tuple(
        _evaluate_profile(profile, context, snapshot, scoring_policy)
        for profile in registry.list_profiles(include_disabled=True)
    )
    eligible = tuple(candidate for candidate in candidates if candidate.trace.eligible)
    eligible_non_fallback = tuple(candidate for candidate in eligible if candidate.profile.fallback_tier == 0)
    eligible_fallback = tuple(candidate for candidate in eligible if candidate.profile.fallback_tier > 0)
    selectable = eligible_non_fallback or eligible_fallback

    if not selectable:
        trace = _build_trace(
            registry=registry,
            policy=scoring_policy,
            candidates=tuple(candidate.trace for candidate in candidates),
            selected=None,
            fallback_used=False,
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
    )
    profile = selected.profile
    matched_rules = tuple(
        sorted(
            set(selected.trace.matched_required_tags)
            | set(selected.trace.matched_preferred_tags)
            | set(selected.trace.matched_source_requirements)
        )
    )
    return VisualStrategyDecision(
        strategy_id=profile.strategy_id,
        archetype=profile.archetype,
        composition_template_id=profile.composition_template_id,
        mood_preset_id=profile.mood_preset_id,
        copy_tone_profile_id=profile.copy_tone_profile_id,
        provider_capabilities=profile.provider_capabilities,
        score=selected.trace.score,
        fallback_used=fallback_used,
        fallback_tier=profile.fallback_tier,
        matched_rules=matched_rules,
        rejected_strategy_ids=tuple(trace.strategy_id for trace in trace.candidates if not trace.eligible),
        registry_version=registry.version,
        registry_snapshot_hash=registry.snapshot_hash,
        resolver_version=RESOLVER_VERSION,
        trace=trace,
    )


def build_visual_strategy_signal_snapshot(
    context: CreativeRoutingContext,
    intent: VisualSemanticIntent,
    *,
    runtime: VisualStrategyRuntimeContext | None = None,
) -> VisualStrategySignalSnapshot:
    runtime_context = runtime or VisualStrategyRuntimeContext()
    placement = runtime_context.placement or str(context.ad_format.ad_format)
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
    product_visual_signals = _normalized_set(
        [
            *context.product_visual.product_tags,
            *context.product_visual.visible_attributes,
            *context.product_visual.explicit_preparation_methods,
            *context.product_visual.permissible_visual_inferences,
        ]
    )
    semantic_intent_signals = _normalized_set(
        [
            *intent.desired_moods,
            *intent.desired_materials,
            *intent.lighting_preferences,
            *intent.composition_preferences,
            *intent.required_visual_facts,
            intent.copy_presence_mode,
        ]
    )
    prohibited = _normalized_set([*context.product_visual.prohibited_visual_inferences, *intent.prohibited_visual_elements])
    reference_signals = _reference_style_signals(context.reference_style_profile)
    all_signals = business_signals | product_signals | product_visual_signals | semantic_intent_signals
    return VisualStrategySignalSnapshot(
        business_signals=business_signals,
        product_signals=product_signals,
        product_visual_signals=product_visual_signals,
        semantic_intent_signals=semantic_intent_signals,
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

    matched_source, missing_source = _evaluate_source_requirements(profile.required_tag_requirements, snapshot)
    if missing_source:
        rejection_codes.append(VisualStrategyRejectionCode.MISSING_SOURCE_REQUIREMENT)

    introduced = _key_set(profile.introduced_visual_elements)
    blocked_elements = introduced & snapshot.prohibited_visual_elements
    if blocked_elements:
        rejection_codes.append(VisualStrategyRejectionCode.PROHIBITED_VISUAL_ELEMENT)

    matched_element_requirements, missing_element_requirements = _evaluate_element_requirements(
        profile.visual_element_evidence_requirements,
        snapshot,
    )
    if missing_element_requirements:
        rejection_codes.append(VisualStrategyRejectionCode.MISSING_VISUAL_ELEMENT_EVIDENCE)
    evidence_backed_elements = frozenset(_key(item.element) for item in profile.visual_element_evidence_requirements)
    unsupported_elements = introduced - evidence_backed_elements - blocked_elements

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
        rejection_codes=tuple(dict.fromkeys(rejection_codes)),
        matched_required_tags=matched_required,
        missing_required_tags=missing_required,
        matched_preferred_tags=matched_preferred,
        matched_excluded_tags=matched_excluded,
        matched_source_requirements=tuple(sorted([*matched_source, *matched_element_requirements])),
        missing_source_requirements=tuple(sorted([*missing_source, *missing_element_requirements])),
        blocked_visual_elements=blocked_elements,
        unsupported_visual_elements=unsupported_elements,
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
    product_relevant_signals = snapshot.product_signals | snapshot.product_visual_signals | snapshot.semantic_intent_signals
    product_targets = _key_set(profile.required_tags) | _key_set(profile.preferred_tags) | _requirement_tokens(profile.required_tag_requirements) | _element_requirement_tokens(profile.visual_element_evidence_requirements)
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
) -> VisualStrategyResolutionTrace:
    eligible_count = sum(1 for candidate in candidates if candidate.eligible)
    return VisualStrategyResolutionTrace(
        resolver_version=RESOLVER_VERSION,
        scoring_policy_version=policy.version,
        registry_version=registry.version,
        registry_snapshot_hash=registry.snapshot_hash,
        candidate_count=len(candidates),
        eligible_count=eligible_count,
        non_fallback_eligible_count=sum(1 for candidate in candidates if candidate.eligible and registry.get(candidate.strategy_id).fallback_tier == 0),
        fallback_eligible_count=sum(1 for candidate in candidates if candidate.eligible and registry.get(candidate.strategy_id).fallback_tier > 0),
        selected_strategy_id=selected.profile.strategy_id if selected else None,
        fallback_used=fallback_used,
        candidates=candidates,
    )


def _evaluate_source_requirements(
    requirements: Iterable[VisualStrategyTagRequirement],
    snapshot: VisualStrategySignalSnapshot,
) -> tuple[list[str], list[str]]:
    matched: list[str] = []
    missing: list[str] = []
    for index, requirement in enumerate(requirements):
        signals = _signals_for_source(requirement.source, snapshot)
        label = _requirement_label("source", index, requirement)
        if _requirement_matches(requirement, signals):
            matched.append(label)
        else:
            missing.append(label)
    return matched, missing


def _evaluate_element_requirements(
    requirements: Iterable[VisualElementEvidenceRequirement],
    snapshot: VisualStrategySignalSnapshot,
) -> tuple[list[str], list[str]]:
    matched: list[str] = []
    missing: list[str] = []
    for index, element_requirement in enumerate(requirements):
        label = f"element:{_key(element_requirement.element)}:{index}"
        if all(_requirement_matches(requirement, _signals_for_source(requirement.source, snapshot)) for requirement in element_requirement.requirements):
            matched.append(label)
        else:
            missing.append(label)
    return matched, missing


def _requirement_matches(requirement: VisualStrategyTagRequirement, signals: frozenset[str]) -> bool:
    all_of = _key_set(requirement.all_of)
    any_of = _key_set(requirement.any_of)
    return all_of <= signals and (not any_of or bool(any_of & signals))


def _signals_for_source(source: VisualStrategyContextSource, snapshot: VisualStrategySignalSnapshot) -> frozenset[str]:
    return {
        VisualStrategyContextSource.BUSINESS: snapshot.business_signals,
        VisualStrategyContextSource.PRODUCT: snapshot.product_signals,
        VisualStrategyContextSource.PRODUCT_VISUAL: snapshot.product_visual_signals,
        VisualStrategyContextSource.SEMANTIC_INTENT: snapshot.semantic_intent_signals,
    }[source]


def _requirement_label(prefix: str, index: int, requirement: VisualStrategyTagRequirement) -> str:
    tokens = sorted(_key_set(requirement.all_of) | _key_set(requirement.any_of))
    return f"{prefix}:{requirement.source.value}:{index}:{','.join(tokens)}"


def _requirement_tokens(requirements: Iterable[VisualStrategyTagRequirement]) -> frozenset[str]:
    return frozenset(token for requirement in requirements for token in (_key_set(requirement.all_of) | _key_set(requirement.any_of)))


def _element_requirement_tokens(requirements: Iterable[VisualElementEvidenceRequirement]) -> frozenset[str]:
    return frozenset(token for requirement in requirements for token in _requirement_tokens(requirement.requirements))


def _coverage(targets: frozenset[str], signals: frozenset[str], unrestricted: float) -> float:
    return len(targets & signals) / len(targets) if targets else unrestricted


def _normalized_set(values: Iterable[Any]) -> frozenset[str]:
    return frozenset(_key(value) for value in values if value is not None and _key(value))


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
