"""Deterministic visual routing trace builders."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any, cast

from orchestrator.app.llm.visual_routing_shadow import VisualRoutingModeExecution
from orchestrator.app.schemas.creative_routing import CreativeRoutingContext
from orchestrator.app.schemas.visual_routing_shadow import (
    LegacyVisualRouteObservation,
    RoutingMode,
    RoutingSource,
    ShadowRoutingErrorStage,
)
from orchestrator.app.schemas.visual_routing_trace import (
    VISUAL_ROUTING_TRACE_VERSION,
    ActiveVisualRouteSummary,
    CanonicalVisualRoutingTrace,
    CanonicalVisualStrategySummary,
    LegacyVisualRoutingTrace,
    ShadowVisualRoutingTrace,
    VisualRoutingDiagnosticStage,
    VisualRoutingInputSnapshot,
    VisualRoutingStageObservation,
    VisualRoutingStageStatus,
    VisualRoutingTrace,
    VisualRoutingTraceCompleteness,
    normalize_trace_strings,
)
from orchestrator.app.schemas.visual_strategy_integrity import RegistryValidationReport
from orchestrator.app.schemas.visual_strategy_resolution import VisualStrategyDecision, VisualStrategyRuntimeContext


class VisualRoutingTraceBuildError(ValueError):
    pass


def summarize_visual_strategy_decision(decision: VisualStrategyDecision) -> CanonicalVisualStrategySummary:
    return CanonicalVisualStrategySummary(
        strategy_id=decision.strategy_id,
        archetype=decision.archetype,
        template_id=decision.composition_template_id,
        preset_id=decision.mood_preset_id,
        copy_tone_profile_id=decision.copy_tone_profile_id,
        route_version=decision.route_version,
        resolver_version=decision.resolver_version,
        registry_version=decision.registry_version,
        registry_snapshot_hash=decision.registry_snapshot_hash,
        matched_rules=decision.matched_rules,
        rejected_strategy_ids=decision.rejected_strategy_ids,
        eligible_not_selected_strategy_ids=decision.eligible_not_selected_strategy_ids,
        fallback_used=decision.fallback_used,
        fallback_role=decision.fallback_role,
        fallback_reason=decision.fallback_reason,
        unsupported_domain=decision.unsupported_domain,
        missing_specialized_profile=decision.missing_specialized_profile,
        confidence=decision.confidence,
        total_score=decision.score.total_score,
        evidence_refs=decision.evidence_refs,
    )


def build_visual_routing_trace(
    *,
    execution: VisualRoutingModeExecution[Any],
    context: CreativeRoutingContext,
    raw_business_type: str | None,
    runtime_context: VisualStrategyRuntimeContext | None = None,
    campaign_roles: Iterable[str] = (),
    placement: str | None = None,
    legacy_observation: LegacyVisualRouteObservation | None = None,
    stage_observations: Iterable[VisualRoutingStageObservation] = (),
    additional_evidence_refs: Iterable[str] = (),
) -> VisualRoutingTrace:
    if execution.mode == RoutingMode.LEGACY:
        return _build_legacy_trace(
            execution=execution,
            context=context,
            raw_business_type=raw_business_type,
            runtime_context=runtime_context,
            campaign_roles=campaign_roles,
            placement=placement,
            explicit_legacy_observation=legacy_observation,
            stage_observations=stage_observations,
            additional_evidence_refs=additional_evidence_refs,
        )
    if execution.mode == RoutingMode.SHADOW:
        return _build_shadow_trace(
            execution=execution,
            context=context,
            raw_business_type=raw_business_type,
            runtime_context=runtime_context,
            campaign_roles=campaign_roles,
            placement=placement,
            explicit_legacy_observation=legacy_observation,
            stage_observations=stage_observations,
            additional_evidence_refs=additional_evidence_refs,
        )
    return _build_canonical_trace(
        execution=execution,
        context=context,
        raw_business_type=raw_business_type,
        runtime_context=runtime_context,
        campaign_roles=campaign_roles,
        placement=placement,
        stage_observations=stage_observations,
        additional_evidence_refs=additional_evidence_refs,
    )


def build_registry_stage_observation(report: RegistryValidationReport) -> VisualRoutingStageObservation:
    if report.valid and report.complete:
        status = VisualRoutingStageStatus.SUCCEEDED
    elif report.valid:
        status = VisualRoutingStageStatus.UNAVAILABLE
    else:
        status = VisualRoutingStageStatus.FAILED
    return VisualRoutingStageObservation(
        stage=VisualRoutingDiagnosticStage.RESOURCE_REGISTRY,
        status=status,
        diagnostic_codes=tuple(issue.code for issue in report.issues),
        error_type="RegistryValidationError" if status == VisualRoutingStageStatus.FAILED else None,
    )


def _build_legacy_trace(
    *,
    execution: VisualRoutingModeExecution[Any],
    context: CreativeRoutingContext,
    raw_business_type: str | None,
    runtime_context: VisualStrategyRuntimeContext | None,
    campaign_roles: Iterable[str],
    placement: str | None,
    explicit_legacy_observation: LegacyVisualRouteObservation | None,
    stage_observations: Iterable[VisualRoutingStageObservation],
    additional_evidence_refs: Iterable[str],
) -> LegacyVisualRoutingTrace:
    if execution.active_source != RoutingSource.LEGACY:
        raise VisualRoutingTraceBuildError("legacy trace requires legacy active source")
    legacy = _select_legacy_observation(explicit_legacy_observation, execution.legacy_observation)
    if legacy is None:
        raise VisualRoutingTraceBuildError("legacy trace requires legacy observation")
    return LegacyVisualRoutingTrace(
        trace_version=VISUAL_ROUTING_TRACE_VERSION,
        routing_mode=RoutingMode.LEGACY,
        completeness=VisualRoutingTraceCompleteness.COMPLETE,
        input_snapshot=_input_snapshot(context, raw_business_type, runtime_context, campaign_roles, placement, legacy, additional_evidence_refs),
        active_route=_active_from_legacy(legacy),
        stage_observations=tuple(stage_observations),
        legacy_observation=legacy,
    )


def _build_shadow_trace(
    *,
    execution: VisualRoutingModeExecution[Any],
    context: CreativeRoutingContext,
    raw_business_type: str | None,
    runtime_context: VisualStrategyRuntimeContext | None,
    campaign_roles: Iterable[str],
    placement: str | None,
    explicit_legacy_observation: LegacyVisualRouteObservation | None,
    stage_observations: Iterable[VisualRoutingStageObservation],
    additional_evidence_refs: Iterable[str],
) -> ShadowVisualRoutingTrace:
    if execution.active_source != RoutingSource.LEGACY:
        raise VisualRoutingTraceBuildError("shadow trace requires legacy active source")
    legacy = _select_legacy_observation(explicit_legacy_observation, execution.legacy_observation)
    if legacy is None:
        active = None
    else:
        active = _active_from_legacy(legacy)
    canonical = summarize_visual_strategy_decision(execution.canonical_decision) if execution.canonical_decision is not None else None
    completeness = VisualRoutingTraceCompleteness.PARTIAL if execution.shadow_error is not None else VisualRoutingTraceCompleteness.COMPLETE
    trace = ShadowVisualRoutingTrace(
        trace_version=VISUAL_ROUTING_TRACE_VERSION,
        routing_mode=RoutingMode.SHADOW,
        completeness=completeness,
        input_snapshot=_input_snapshot(context, raw_business_type, runtime_context, campaign_roles, placement, legacy, additional_evidence_refs),
        active_route=active,
        stage_observations=_with_shadow_error_stage(stage_observations, execution.shadow_error),
        legacy_observation=legacy,
        canonical_decision=canonical,
        route_disagreement=execution.comparison,
        shadow_error=execution.shadow_error,
    )
    if execution.comparison is not None and canonical is not None and legacy is not None:
        return trace
    if execution.shadow_error is None:
        raise VisualRoutingTraceBuildError("successful shadow trace requires comparison data")
    return trace


def _build_canonical_trace(
    *,
    execution: VisualRoutingModeExecution[Any],
    context: CreativeRoutingContext,
    raw_business_type: str | None,
    runtime_context: VisualStrategyRuntimeContext | None,
    campaign_roles: Iterable[str],
    placement: str | None,
    stage_observations: Iterable[VisualRoutingStageObservation],
    additional_evidence_refs: Iterable[str],
) -> CanonicalVisualRoutingTrace:
    if execution.active_source != RoutingSource.CANONICAL:
        raise VisualRoutingTraceBuildError("canonical trace requires canonical active source")
    if execution.canonical_decision is None:
        raise VisualRoutingTraceBuildError("canonical trace requires canonical decision")
    canonical = summarize_visual_strategy_decision(execution.canonical_decision)
    return CanonicalVisualRoutingTrace(
        trace_version=VISUAL_ROUTING_TRACE_VERSION,
        routing_mode=RoutingMode.CANONICAL,
        completeness=VisualRoutingTraceCompleteness.COMPLETE,
        input_snapshot=_input_snapshot(context, raw_business_type, runtime_context, campaign_roles, placement, None, additional_evidence_refs),
        active_route=_active_from_canonical(canonical),
        stage_observations=tuple(stage_observations),
        canonical_decision=canonical,
    )


def _input_snapshot(
    context: CreativeRoutingContext,
    raw_business_type: str | None,
    runtime_context: VisualStrategyRuntimeContext | None,
    campaign_roles: Iterable[str],
    placement: str | None,
    legacy: LegacyVisualRouteObservation | None,
    additional_evidence_refs: Iterable[str],
) -> VisualRoutingInputSnapshot:
    resolved_raw_business_type = _resolve_raw_business_type(context, raw_business_type)
    resolved_campaign_roles = _resolve_campaign_roles(runtime_context, campaign_roles)
    resolved_placement = _resolve_placement(context, runtime_context, placement)
    conflict_ids = [conflict.conflict_id for conflict in context.input_conflicts]
    conflict_types = [conflict.conflict_type for conflict in context.input_conflicts]
    product_category_path = tuple(context.product.category_path)
    product_visual_category_path = tuple(context.product_visual.category_path)
    evidence_refs = [
        *context.domain.evidence_refs,
        *context.business.evidence_refs,
        *context.product.product_name_evidence_ids,
        *(fact.evidence_id for fact in context.product.verified_facts),
        *(observation.evidence_id for observation in context.product.visual_observations),
        *context.product_visual.evidence_refs,
        *context.campaign.evidence_refs,
        *additional_evidence_refs,
    ]
    return VisualRoutingInputSnapshot(
        raw_business_type=resolved_raw_business_type,
        canonical_domain=context.domain.canonical_domain,
        legacy_visual_key=legacy.legacy_route_key if legacy is not None else None,
        product_name=context.product.product_name,
        product_category_path=product_category_path,
        product_visual_category_path=product_visual_category_path,
        category_path_match=product_category_path == product_visual_category_path,
        business_tags=context.business.business_tags,
        product_tags=context.product_visual.product_tags,
        campaign_roles=resolved_campaign_roles,
        placement=resolved_placement,
        ambiguity_flags=context.ambiguity_flags,
        input_conflict_ids=conflict_ids,
        input_conflict_types=conflict_types,
        evidence_refs=evidence_refs,
    )


def _resolve_raw_business_type(context: CreativeRoutingContext, raw_business_type: str | None) -> str | None:
    context_raw = context.domain.raw_business_type
    if raw_business_type is not None and context_raw is not None and raw_business_type.strip() != context_raw.strip():
        raise VisualRoutingTraceBuildError("raw business type sources conflict")
    return context_raw if context_raw is not None else raw_business_type


def _resolve_campaign_roles(
    runtime_context: VisualStrategyRuntimeContext | None,
    campaign_roles: Iterable[str],
) -> tuple[str, ...]:
    explicit = normalize_trace_strings(campaign_roles)
    if runtime_context is None:
        return explicit
    runtime_roles = tuple(sorted(runtime_context.campaign_roles))
    if explicit and explicit != runtime_roles:
        raise VisualRoutingTraceBuildError("campaign role sources conflict")
    return runtime_roles


def _resolve_placement(
    context: CreativeRoutingContext,
    runtime_context: VisualStrategyRuntimeContext | None,
    placement: str | None,
) -> str | None:
    context_placement = str(context.ad_format.ad_format)
    runtime_placement = runtime_context.placement if runtime_context is not None else None
    if runtime_placement is not None and context_placement != runtime_placement:
        raise VisualRoutingTraceBuildError("runtime placement conflicts with AdFormatSpec")
    baseline = runtime_placement if runtime_placement is not None else context_placement
    if placement is not None and baseline is not None and placement.strip() != str(baseline).strip():
        raise VisualRoutingTraceBuildError("placement sources conflict")
    if placement is not None:
        return placement
    if baseline is not None:
        return cast(str, baseline)
    return None


def _select_legacy_observation(
    explicit: LegacyVisualRouteObservation | None,
    execution_observation: LegacyVisualRouteObservation | None,
) -> LegacyVisualRouteObservation | None:
    if explicit is not None and execution_observation is not None and explicit != execution_observation:
        raise VisualRoutingTraceBuildError("legacy observation sources conflict")
    return explicit if explicit is not None else execution_observation


def _active_from_legacy(legacy: LegacyVisualRouteObservation) -> ActiveVisualRouteSummary:
    return ActiveVisualRouteSummary(
        source=RoutingSource.LEGACY,
        strategy_id=None,
        template_id=legacy.template_id,
        preset_id=legacy.preset_id,
        copy_tone_profile_id=legacy.copy_tone_profile_id,
        route_version=legacy.route_version,
    )


def _active_from_canonical(canonical: CanonicalVisualStrategySummary) -> ActiveVisualRouteSummary:
    return ActiveVisualRouteSummary(
        source=RoutingSource.CANONICAL,
        strategy_id=canonical.strategy_id,
        template_id=canonical.template_id,
        preset_id=canonical.preset_id,
        copy_tone_profile_id=canonical.copy_tone_profile_id,
        route_version=canonical.route_version,
    )


def _with_shadow_error_stage(
    observations: Iterable[VisualRoutingStageObservation],
    shadow_error: Any,
) -> tuple[VisualRoutingStageObservation, ...]:
    items = list(observations)
    if shadow_error is None:
        return tuple(items)
    if shadow_error.stage == ShadowRoutingErrorStage.CANONICAL_RESOLUTION:
        return _upsert_stage_observation(
            items,
            VisualRoutingStageObservation(
                stage=VisualRoutingDiagnosticStage.STRATEGY_RESOLUTION,
                status=VisualRoutingStageStatus.FAILED,
                diagnostic_codes=(shadow_error.code.value,),
                error_type=shadow_error.exception_type,
            ),
        )
    if shadow_error.stage == ShadowRoutingErrorStage.ROUTE_COMPARISON:
        return _upsert_stage_observation(
            items,
            VisualRoutingStageObservation(
                stage=VisualRoutingDiagnosticStage.ROUTE_COMPARISON,
                status=VisualRoutingStageStatus.DEGRADED,
                diagnostic_codes=(shadow_error.code.value,),
            ),
        )
    return tuple(items)


def _upsert_stage_observation(
    observations: list[VisualRoutingStageObservation],
    new_observation: VisualRoutingStageObservation,
) -> tuple[VisualRoutingStageObservation, ...]:
    merged: list[VisualRoutingStageObservation] = []
    replaced = False
    for observation in observations:
        if observation.stage != new_observation.stage:
            merged.append(observation)
            continue
        merged.append(
            VisualRoutingStageObservation(
                stage=observation.stage,
                status=new_observation.status,
                diagnostic_codes=(*observation.diagnostic_codes, *new_observation.diagnostic_codes),
                evidence_refs=observation.evidence_refs,
                artifact_refs=observation.artifact_refs,
                error_type=new_observation.error_type or observation.error_type,
            )
        )
        replaced = True
    if not replaced:
        merged.append(new_observation)
    return tuple(merged)
