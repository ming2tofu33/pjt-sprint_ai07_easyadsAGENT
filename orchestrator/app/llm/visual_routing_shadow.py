"""Shadow execution helpers for comparing legacy and canonical visual routing."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Generic, Protocol, TypeVar

from orchestrator.app.llm.visual_strategy_resolver import NoEligibleVisualStrategyError
from orchestrator.app.schemas.visual_routing_shadow import (
    LegacyVisualRouteObservation,
    RouteComparison,
    RouteComparisonLimitation,
    RouteComparisonPolicy,
    RouteComparisonSeverity,
    RouteDisagreementCode,
    RoutingExecutionPlan,
    RoutingFailurePolicy,
    RoutingMode,
    RoutingSource,
    ShadowRoutingError,
    ShadowRoutingErrorCode,
    ShadowRoutingErrorStage,
    build_default_route_comparison_policy,
)
from orchestrator.app.schemas.visual_strategy_resolution import VisualStrategyDecision


COMPARISON_VERSION = "visual-route-comparison-v1"

LegacyResultT = TypeVar("LegacyResultT")


class VisualRouteFamilyResolver(Protocol):
    def resolve_family(self, preset_id: str, template_id: str) -> str | None:
        """Return explicit route family metadata for a preset/template pair."""


@dataclass(frozen=True)
class VisualRoutingModeExecution(Generic[LegacyResultT]):
    mode: RoutingMode
    active_source: RoutingSource
    legacy_result: LegacyResultT | None = None
    legacy_observation: LegacyVisualRouteObservation | None = None
    canonical_decision: VisualStrategyDecision | None = None
    comparison: RouteComparison | None = None
    shadow_error: ShadowRoutingError | None = None

    @property
    def active_result(self) -> LegacyResultT | VisualStrategyDecision:
        if self.active_source == RoutingSource.LEGACY and self.legacy_result is not None:
            return self.legacy_result
        if self.active_source == RoutingSource.CANONICAL and self.canonical_decision is not None:
            return self.canonical_decision
        raise ValueError("active result is unavailable")


def build_routing_execution_plan(mode: RoutingMode) -> RoutingExecutionPlan:
    if mode == RoutingMode.LEGACY:
        return RoutingExecutionPlan(
            mode=mode,
            run_legacy=True,
            run_canonical=False,
            active_source=RoutingSource.LEGACY,
            canonical_failure_policy=RoutingFailurePolicy.NOT_APPLICABLE,
        )
    if mode == RoutingMode.SHADOW:
        return RoutingExecutionPlan(
            mode=mode,
            run_legacy=True,
            run_canonical=True,
            active_source=RoutingSource.LEGACY,
            canonical_failure_policy=RoutingFailurePolicy.FAIL_OPEN,
        )
    return RoutingExecutionPlan(
        mode=mode,
        run_legacy=False,
        run_canonical=True,
        active_source=RoutingSource.CANONICAL,
        canonical_failure_policy=RoutingFailurePolicy.FAIL_CLOSED,
    )


def compare_visual_routes(
    legacy: LegacyVisualRouteObservation,
    canonical: VisualStrategyDecision,
    *,
    family_resolver: VisualRouteFamilyResolver | None = None,
    policy: RouteComparisonPolicy | None = None,
) -> RouteComparison:
    policy = policy or build_default_route_comparison_policy()
    codes: list[RouteDisagreementCode] = []
    limitations: list[RouteComparisonLimitation] = []

    preset_match = legacy.preset_id == canonical.mood_preset_id
    if not preset_match:
        codes.append(RouteDisagreementCode.PRESET_MISMATCH)

    template_match = legacy.template_id == canonical.composition_template_id
    if not template_match:
        codes.append(RouteDisagreementCode.TEMPLATE_MISMATCH)

    copy_tone_match = None
    if legacy.copy_tone_profile_id is not None:
        copy_tone_match = legacy.copy_tone_profile_id == canonical.copy_tone_profile_id
        if not copy_tone_match:
            codes.append(RouteDisagreementCode.COPY_TONE_MISMATCH)

    legacy_family_id = legacy.route_family_id
    new_family_id = None
    family_match = None
    if family_resolver is None:
        limitations.append(RouteComparisonLimitation.FAMILY_METADATA_UNAVAILABLE)
    else:
        if legacy_family_id is None:
            legacy_family_id = family_resolver.resolve_family(legacy.preset_id, legacy.template_id)
        new_family_id = family_resolver.resolve_family(canonical.mood_preset_id, canonical.composition_template_id)
        if legacy_family_id is None or new_family_id is None:
            limitations.append(RouteComparisonLimitation.FAMILY_METADATA_UNAVAILABLE)
        else:
            family_match = legacy_family_id == new_family_id
            if not family_match:
                codes.append(RouteDisagreementCode.FAMILY_MISMATCH)

    return RouteComparison(
        comparison_version=COMPARISON_VERSION,
        comparison_policy_version=policy.version,
        legacy_route_key=legacy.legacy_route_key,
        legacy_route_version=legacy.route_version,
        legacy_preset_id=legacy.preset_id,
        legacy_template_id=legacy.template_id,
        legacy_copy_tone_profile_id=legacy.copy_tone_profile_id,
        new_strategy_id=canonical.strategy_id,
        new_preset_id=canonical.mood_preset_id,
        new_template_id=canonical.composition_template_id,
        new_copy_tone_profile_id=canonical.copy_tone_profile_id,
        legacy_family_id=legacy_family_id,
        new_family_id=new_family_id,
        preset_match=preset_match,
        template_match=template_match,
        copy_tone_match=copy_tone_match,
        family_match=family_match,
        disagreement_codes=tuple(codes),
        comparison_limitations=tuple(limitations),
        severity=_comparison_severity(tuple(codes), policy),
        new_route_version=canonical.route_version,
        new_resolver_version=canonical.resolver_version,
        new_registry_version=canonical.registry_version,
        new_registry_snapshot_hash=canonical.registry_snapshot_hash,
        canonical_fallback_used=canonical.fallback_used,
        canonical_fallback_role=canonical.fallback_role,
        canonical_fallback_reason=canonical.fallback_reason,
        canonical_unsupported_domain=canonical.unsupported_domain,
        canonical_missing_specialized_profile=canonical.missing_specialized_profile,
    )


def execute_visual_routing_mode(
    mode: RoutingMode,
    *,
    legacy_runner: Callable[[], LegacyResultT] | None = None,
    legacy_observer: Callable[[LegacyResultT], LegacyVisualRouteObservation] | None = None,
    canonical_runner: Callable[[], VisualStrategyDecision] | None = None,
    family_resolver: VisualRouteFamilyResolver | None = None,
    comparison_policy: RouteComparisonPolicy | None = None,
) -> VisualRoutingModeExecution[LegacyResultT]:
    plan = build_routing_execution_plan(mode)

    if plan.mode == RoutingMode.LEGACY:
        if legacy_runner is None:
            raise ValueError("legacy_runner is required")
        legacy_result = legacy_runner()
        return VisualRoutingModeExecution(
            mode=mode,
            active_source=RoutingSource.LEGACY,
            legacy_result=legacy_result,
        )

    if plan.mode == RoutingMode.CANONICAL:
        if canonical_runner is None:
            raise ValueError("canonical_runner is required")
        canonical_decision = canonical_runner()
        return VisualRoutingModeExecution(
            mode=mode,
            active_source=RoutingSource.CANONICAL,
            canonical_decision=canonical_decision,
        )

    if legacy_runner is None:
        raise ValueError("legacy_runner is required")
    if legacy_observer is None:
        raise ValueError("legacy_observer is required")
    if canonical_runner is None:
        raise ValueError("canonical_runner is required")

    legacy_result = legacy_runner()
    try:
        canonical_decision = canonical_runner()
    except NoEligibleVisualStrategyError as exc:
        return _shadow_fail_open(
            mode=mode,
            legacy_result=legacy_result,
            stage=ShadowRoutingErrorStage.CANONICAL_RESOLUTION,
            code=ShadowRoutingErrorCode.NO_ELIGIBLE_CANONICAL_STRATEGY,
            exc=exc,
        )
    except Exception as exc:
        return _shadow_fail_open(
            mode=mode,
            legacy_result=legacy_result,
            stage=ShadowRoutingErrorStage.CANONICAL_RESOLUTION,
            code=ShadowRoutingErrorCode.CANONICAL_RESOLUTION_FAILED,
            exc=exc,
        )

    try:
        legacy_observation = legacy_observer(legacy_result)
    except Exception as exc:
        return _shadow_fail_open(
            mode=mode,
            legacy_result=legacy_result,
            canonical_decision=canonical_decision,
            stage=ShadowRoutingErrorStage.LEGACY_OBSERVATION,
            code=ShadowRoutingErrorCode.LEGACY_OBSERVATION_FAILED,
            exc=exc,
        )

    try:
        comparison = compare_visual_routes(
            legacy_observation,
            canonical_decision,
            family_resolver=family_resolver,
            policy=comparison_policy,
        )
    except Exception as exc:
        return _shadow_fail_open(
            mode=mode,
            legacy_result=legacy_result,
            legacy_observation=legacy_observation,
            canonical_decision=canonical_decision,
            stage=ShadowRoutingErrorStage.ROUTE_COMPARISON,
            code=ShadowRoutingErrorCode.ROUTE_COMPARISON_FAILED,
            exc=exc,
        )

    return VisualRoutingModeExecution(
        mode=mode,
        active_source=RoutingSource.LEGACY,
        legacy_result=legacy_result,
        legacy_observation=legacy_observation,
        canonical_decision=canonical_decision,
        comparison=comparison,
    )


def _comparison_severity(
    codes: tuple[RouteDisagreementCode, ...],
    policy: RouteComparisonPolicy,
) -> RouteComparisonSeverity:
    resource_mismatches = {
        RouteDisagreementCode.PRESET_MISMATCH,
        RouteDisagreementCode.TEMPLATE_MISMATCH,
        RouteDisagreementCode.COPY_TONE_MISMATCH,
    }
    if not codes:
        return RouteComparisonSeverity.NONE
    if RouteDisagreementCode.FAMILY_MISMATCH in codes:
        return policy.family_mismatch_severity
    mismatch_count = len(resource_mismatches.intersection(codes))
    if mismatch_count >= 2:
        return policy.multiple_resource_mismatch_severity
    if mismatch_count == 1:
        return policy.single_resource_mismatch_severity
    return policy.single_resource_mismatch_severity


def _shadow_fail_open(
    *,
    mode: RoutingMode,
    legacy_result: LegacyResultT,
    stage: ShadowRoutingErrorStage,
    code: ShadowRoutingErrorCode,
    exc: Exception,
    legacy_observation: LegacyVisualRouteObservation | None = None,
    canonical_decision: VisualStrategyDecision | None = None,
) -> VisualRoutingModeExecution[LegacyResultT]:
    return VisualRoutingModeExecution(
        mode=mode,
        active_source=RoutingSource.LEGACY,
        legacy_result=legacy_result,
        legacy_observation=legacy_observation,
        canonical_decision=canonical_decision,
        shadow_error=ShadowRoutingError(
            stage=stage,
            code=code,
            exception_type=exc.__class__.__name__,
        ),
    )
