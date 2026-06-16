from __future__ import annotations

import json

import pytest
from pydantic import ValidationError

from orchestrator.app.llm.domain_routing import LegacyVisualRouteKey
from orchestrator.app.llm.visual_routing_shadow import (
    build_routing_execution_plan,
    compare_visual_routes,
    execute_visual_routing_mode,
)
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
    ShadowRoutingErrorCode,
    ShadowRoutingErrorStage,
)
from orchestrator.app.schemas.visual_strategy_resolution import (
    VisualStrategyCandidateTrace,
    VisualStrategyDecision,
    VisualStrategyFallbackReason,
    VisualStrategyResolutionTrace,
    VisualStrategyScore,
)


def _score(total: float = 0.9) -> VisualStrategyScore:
    return VisualStrategyScore(
        evidence_alignment=1.0,
        product_relevance=1.0,
        campaign_fit=1.0,
        format_fit=1.0,
        environment_fit=1.0,
        reference_fit=1.0,
        semantic_fit=1.0,
        unsupported_inference_penalty=0.0,
        fallback_penalty=0.0,
        total_score=total,
    )


def _decision(
    *,
    strategy_id: str = "strategy.editorial",
    preset_id: str = "preset.editorial",
    template_id: str = "template.editorial",
    copy_tone_profile_id: str = "copy.direct",
    fallback_used: bool = False,
) -> VisualStrategyDecision:
    fallback_tier = 1 if fallback_used else 0
    fallback_role = "product_editorial" if fallback_used else None
    fallback_reason = VisualStrategyFallbackReason.MISSING_SPECIALIZED_PROFILE if fallback_used else None
    score = _score()
    candidate = VisualStrategyCandidateTrace(
        strategy_id=strategy_id,
        eligible=True,
        fallback_tier=fallback_tier,
        fallback_role=fallback_role,
        score=score,
    )
    trace = VisualStrategyResolutionTrace(
        resolver_version="visual-strategy-resolver-v3",
        scoring_policy_version="visual-strategy-scoring-v2",
        registry_version="visual-strategy-registry-v2",
        registry_snapshot_hash="registry-hash",
        candidate_count=1,
        eligible_count=1,
        domain_supported_primary_count=0 if fallback_used else 1,
        eligible_primary_count=0 if fallback_used else 1,
        eligible_fallback_count=1 if fallback_used else 0,
        non_fallback_eligible_count=0 if fallback_used else 1,
        fallback_eligible_count=1 if fallback_used else 0,
        selected_strategy_id=strategy_id,
        fallback_used=fallback_used,
        fallback_reason=fallback_reason,
        fallback_role=fallback_role,
        missing_specialized_profile=fallback_used,
        candidates=(candidate,),
    )
    return VisualStrategyDecision(
        strategy_id=strategy_id,
        route_version="visual-strategy-route-v3",
        resolver_version="visual-strategy-resolver-v3",
        archetype="editorial",
        composition_template_id=template_id,
        mood_preset_id=preset_id,
        copy_tone_profile_id=copy_tone_profile_id,
        copy_presence_mode="optional",
        subject_guidance=("show product",),
        environment_guidance=("simple surface",),
        negative_constraints=("no unsupported claim",),
        matched_rules=("rule",),
        rejected_strategy_ids=(),
        eligible_not_selected_strategy_ids=(),
        evidence_refs=("brief",),
        confidence=0.9,
        provider_capabilities=frozenset({"image"}),
        score=score,
        fallback_used=fallback_used,
        fallback_tier=fallback_tier,
        fallback_role=fallback_role,
        fallback_reason=fallback_reason,
        unsupported_domain=False,
        missing_specialized_profile=fallback_used,
        registry_version="visual-strategy-registry-v2",
        registry_snapshot_hash="registry-hash",
        confidence_policy_version="visual-strategy-confidence-v1",
        trace=trace,
    )


def _legacy_observation(
    *,
    preset_id: str = "preset.editorial",
    template_id: str = "template.editorial",
    copy_tone_profile_id: str | None = "copy.direct",
    route_family_id: str | None = "family.editorial",
) -> LegacyVisualRouteObservation:
    return LegacyVisualRouteObservation(
        legacy_route_key=LegacyVisualRouteKey.GENERIC,
        preset_id=preset_id,
        template_id=template_id,
        copy_tone_profile_id=copy_tone_profile_id,
        route_family_id=route_family_id,
        route_version="legacy-route-v1",
    )


class _FamilyResolver:
    def __init__(self, mapping: dict[tuple[str, str], str | None]) -> None:
        self.mapping = mapping

    def resolve_family(self, preset_id: str, template_id: str) -> str | None:
        return self.mapping.get((preset_id, template_id))


class _FailingFamilyResolver:
    def resolve_family(self, preset_id: str, template_id: str) -> str | None:
        raise RuntimeError("family resolver secret")


def test_routing_mode_schema_values_only_extra_forbid_frozen_json_roundtrip() -> None:
    plan = RoutingExecutionPlan(
        mode="shadow",
        run_legacy=True,
        run_canonical=True,
        active_source="legacy",
        canonical_failure_policy="fail_open",
    )

    assert plan.model_dump(mode="json") == json.loads(plan.model_dump_json())
    assert RoutingExecutionPlan.model_validate_json(plan.model_dump_json()) == plan
    with pytest.raises(ValidationError):
        RoutingExecutionPlan(
            mode="mirror",
            run_legacy=True,
            run_canonical=True,
            active_source="legacy",
            canonical_failure_policy="fail_open",
        )
    with pytest.raises(ValidationError):
        RoutingExecutionPlan(
            mode="shadow",
            run_legacy=True,
            run_canonical=True,
            active_source="legacy",
            canonical_failure_policy="fail_open",
            unexpected=True,
        )
    with pytest.raises(ValidationError):
        plan.mode = RoutingMode.LEGACY


@pytest.mark.parametrize(
    ("mode", "expected"),
    [
        (RoutingMode.LEGACY, (True, False, RoutingSource.LEGACY, RoutingFailurePolicy.NOT_APPLICABLE)),
        (RoutingMode.SHADOW, (True, True, RoutingSource.LEGACY, RoutingFailurePolicy.FAIL_OPEN)),
        (RoutingMode.CANONICAL, (False, True, RoutingSource.CANONICAL, RoutingFailurePolicy.FAIL_CLOSED)),
    ],
)
def test_execution_plan_exact_matrix(mode: RoutingMode, expected: tuple[bool, bool, RoutingSource, RoutingFailurePolicy]) -> None:
    plan = build_routing_execution_plan(mode)
    assert (plan.run_legacy, plan.run_canonical, plan.active_source, plan.canonical_failure_policy) == expected


def test_legacy_mode_calls_legacy_only_and_returns_active_identity() -> None:
    calls = {"legacy": 0, "canonical": 0, "observer": 0}
    legacy_result = {"route": "legacy"}

    execution = execute_visual_routing_mode(
        RoutingMode.LEGACY,
        legacy_runner=lambda: calls.__setitem__("legacy", calls["legacy"] + 1) or legacy_result,
        canonical_runner=lambda: calls.__setitem__("canonical", calls["canonical"] + 1) or _decision(),
        legacy_observer=lambda result: calls.__setitem__("observer", calls["observer"] + 1) or _legacy_observation(),
    )

    assert calls == {"legacy": 1, "canonical": 0, "observer": 0}
    assert execution.active_source == RoutingSource.LEGACY
    assert execution.active_result is legacy_result


def test_shadow_success_calls_both_and_keeps_legacy_active_identity() -> None:
    calls = {"legacy": 0, "canonical": 0, "observer": 0}
    legacy_result = {"route": "legacy"}
    canonical = _decision(preset_id="preset.new", template_id="template.new")

    execution = execute_visual_routing_mode(
        RoutingMode.SHADOW,
        legacy_runner=lambda: calls.__setitem__("legacy", calls["legacy"] + 1) or legacy_result,
        canonical_runner=lambda: calls.__setitem__("canonical", calls["canonical"] + 1) or canonical,
        legacy_observer=lambda result: calls.__setitem__("observer", calls["observer"] + 1) or _legacy_observation(),
        family_resolver=_FamilyResolver({}),
    )

    assert calls == {"legacy": 1, "canonical": 1, "observer": 1}
    assert execution.active_result is legacy_result
    assert execution.canonical_decision is canonical
    assert execution.comparison is not None


def test_shadow_canonical_failure_is_sanitized_fail_open() -> None:
    def fail_canonical() -> VisualStrategyDecision:
        raise RuntimeError("provider secret should not leak")

    execution = execute_visual_routing_mode(
        RoutingMode.SHADOW,
        legacy_runner=lambda: "legacy",
        canonical_runner=fail_canonical,
        legacy_observer=lambda result: _legacy_observation(),
    )

    assert execution.active_result == "legacy"
    assert execution.comparison is None
    assert execution.shadow_error is not None
    assert execution.shadow_error.stage == ShadowRoutingErrorStage.CANONICAL_RESOLUTION
    assert execution.shadow_error.code == ShadowRoutingErrorCode.CANONICAL_RESOLUTION_FAILED
    assert execution.shadow_error.exception_type == "RuntimeError"
    assert "secret" not in execution.shadow_error.model_dump_json()


def test_shadow_no_eligible_strategy_gets_specific_error_code() -> None:
    def no_eligible() -> VisualStrategyDecision:
        raise NoEligibleVisualStrategyError(_decision().trace)

    execution = execute_visual_routing_mode(
        RoutingMode.SHADOW,
        legacy_runner=lambda: "legacy",
        canonical_runner=no_eligible,
        legacy_observer=lambda result: _legacy_observation(),
    )

    assert execution.shadow_error is not None
    assert execution.shadow_error.code == ShadowRoutingErrorCode.NO_ELIGIBLE_CANONICAL_STRATEGY


def test_shadow_observation_failure_is_fail_open() -> None:
    execution = execute_visual_routing_mode(
        RoutingMode.SHADOW,
        legacy_runner=lambda: "legacy",
        canonical_runner=lambda: _decision(),
        legacy_observer=lambda result: (_ for _ in ()).throw(RuntimeError("observer secret")),
    )

    assert execution.active_result == "legacy"
    assert execution.comparison is None
    assert execution.shadow_error is not None
    assert execution.shadow_error.stage == ShadowRoutingErrorStage.LEGACY_OBSERVATION
    assert execution.shadow_error.code == ShadowRoutingErrorCode.LEGACY_OBSERVATION_FAILED


def test_shadow_comparison_failure_is_fail_open() -> None:
    execution = execute_visual_routing_mode(
        RoutingMode.SHADOW,
        legacy_runner=lambda: "legacy",
        canonical_runner=lambda: _decision(),
        legacy_observer=lambda result: _legacy_observation(route_family_id=None),
        family_resolver=_FailingFamilyResolver(),
    )

    assert execution.active_result == "legacy"
    assert execution.comparison is None
    assert execution.shadow_error is not None
    assert execution.shadow_error.stage == ShadowRoutingErrorStage.ROUTE_COMPARISON
    assert execution.shadow_error.code == ShadowRoutingErrorCode.ROUTE_COMPARISON_FAILED
    assert "secret" not in execution.shadow_error.model_dump_json()


def test_canonical_mode_calls_canonical_only_and_propagates_failures() -> None:
    canonical = _decision()
    execution = execute_visual_routing_mode(
        RoutingMode.CANONICAL,
        canonical_runner=lambda: canonical,
        legacy_runner=lambda: pytest.fail("legacy must not run"),
        legacy_observer=lambda result: pytest.fail("observer must not run"),
    )
    assert execution.active_result is canonical

    with pytest.raises(RuntimeError, match="canonical failed"):
        execute_visual_routing_mode(
            RoutingMode.CANONICAL,
            canonical_runner=lambda: (_ for _ in ()).throw(RuntimeError("canonical failed")),
        )


@pytest.mark.parametrize("mode", [RoutingMode.LEGACY, RoutingMode.SHADOW])
def test_legacy_runner_failure_propagates_and_shadow_canonical_not_called(mode: RoutingMode) -> None:
    calls = {"canonical": 0}

    with pytest.raises(RuntimeError, match="legacy failed"):
        execute_visual_routing_mode(
            mode,
            legacy_runner=lambda: (_ for _ in ()).throw(RuntimeError("legacy failed")),
            canonical_runner=lambda: calls.__setitem__("canonical", calls["canonical"] + 1) or _decision(),
            legacy_observer=lambda result: _legacy_observation(),
        )

    assert calls["canonical"] == 0


def test_compare_exact_match_has_no_disagreement_with_family_resolver() -> None:
    comparison = compare_visual_routes(
        _legacy_observation(),
        _decision(),
        family_resolver=_FamilyResolver({("preset.editorial", "template.editorial"): "family.editorial"}),
    )

    assert comparison.preset_match is True
    assert comparison.template_match is True
    assert comparison.copy_tone_match is True
    assert comparison.family_match is True
    assert comparison.disagreement_codes == ()
    assert comparison.severity == RouteComparisonSeverity.NONE


@pytest.mark.parametrize(
    ("legacy", "canonical", "code"),
    [
        (_legacy_observation(preset_id="preset.old"), _decision(), RouteDisagreementCode.PRESET_MISMATCH),
        (_legacy_observation(template_id="template.old"), _decision(), RouteDisagreementCode.TEMPLATE_MISMATCH),
        (_legacy_observation(copy_tone_profile_id="copy.old"), _decision(), RouteDisagreementCode.COPY_TONE_MISMATCH),
    ],
)
def test_compare_single_resource_mismatch_is_warning(
    legacy: LegacyVisualRouteObservation,
    canonical: VisualStrategyDecision,
    code: RouteDisagreementCode,
) -> None:
    comparison = compare_visual_routes(
        legacy,
        canonical,
        family_resolver=_FamilyResolver(
            {
                (legacy.preset_id, legacy.template_id): "family.editorial",
                ("preset.editorial", "template.editorial"): "family.editorial",
            }
        ),
    )

    assert code in comparison.disagreement_codes
    assert comparison.severity == RouteComparisonSeverity.WARNING


def test_compare_preset_and_template_mismatch_is_high() -> None:
    comparison = compare_visual_routes(
        _legacy_observation(preset_id="preset.old", template_id="template.old"),
        _decision(),
        family_resolver=_FamilyResolver({("preset.old", "template.old"): "family.same", ("preset.editorial", "template.editorial"): "family.same"}),
    )

    assert comparison.disagreement_codes[:2] == (
        RouteDisagreementCode.PRESET_MISMATCH,
        RouteDisagreementCode.TEMPLATE_MISMATCH,
    )
    assert comparison.severity == RouteComparisonSeverity.HIGH


def test_family_resolver_match_mismatch_and_unavailable() -> None:
    canonical = _decision()
    legacy = _legacy_observation(route_family_id=None)

    matched = compare_visual_routes(
        legacy,
        canonical,
        family_resolver=_FamilyResolver({("preset.editorial", "template.editorial"): "family.same"}),
    )
    assert matched.family_match is True

    mismatched = compare_visual_routes(
        _legacy_observation(route_family_id="family.old"),
        canonical,
        family_resolver=_FamilyResolver({("preset.editorial", "template.editorial"): "family.new"}),
    )
    assert mismatched.family_match is False
    assert RouteDisagreementCode.FAMILY_MISMATCH in mismatched.disagreement_codes
    assert mismatched.severity == RouteComparisonSeverity.HIGH

    unavailable = compare_visual_routes(legacy, canonical)
    assert unavailable.family_match is None
    assert unavailable.disagreement_codes == ()
    assert unavailable.comparison_limitations == (RouteComparisonLimitation.FAMILY_METADATA_UNAVAILABLE,)
    assert unavailable.severity == RouteComparisonSeverity.NONE


def test_family_comparison_does_not_infer_prefix_or_substring_relationships() -> None:
    comparison = compare_visual_routes(
        _legacy_observation(preset_id="preset", template_id="template", route_family_id=None),
        _decision(preset_id="preset.extended", template_id="template.extended"),
        family_resolver=_FamilyResolver({}),
    )

    assert comparison.family_match is None
    assert RouteComparisonLimitation.FAMILY_METADATA_UNAVAILABLE in comparison.comparison_limitations


def test_fallback_metadata_is_preserved_without_extra_disagreement_code() -> None:
    comparison = compare_visual_routes(
        _legacy_observation(),
        _decision(fallback_used=True),
        family_resolver=_FamilyResolver({("preset.editorial", "template.editorial"): "family.editorial"}),
    )

    assert comparison.canonical_fallback_used is True
    assert comparison.canonical_fallback_role == "product_editorial"
    assert comparison.canonical_fallback_reason == "missing_specialized_profile"
    assert comparison.canonical_missing_specialized_profile is True
    assert RouteComparisonLimitation.FAMILY_METADATA_UNAVAILABLE not in comparison.comparison_limitations


def test_comparison_json_is_deterministic_and_strategy_id_does_not_affect_severity() -> None:
    legacy = _legacy_observation()
    resolver = _FamilyResolver({("preset.editorial", "template.editorial"): "family.editorial"})
    first = compare_visual_routes(legacy, _decision(strategy_id="strategy.one"), family_resolver=resolver)
    second = compare_visual_routes(legacy, _decision(strategy_id="strategy.one"), family_resolver=resolver)
    renamed = compare_visual_routes(legacy, _decision(strategy_id="strategy.two"), family_resolver=resolver)

    assert first.model_dump_json() == second.model_dump_json()
    assert first.severity == renamed.severity
    assert first.disagreement_codes == renamed.disagreement_codes


def _comparison_payload(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "comparison_version": "visual-route-comparison-v1",
        "comparison_policy_version": "visual-route-comparison-policy-v1",
        "legacy_route_key": "generic",
        "legacy_route_version": "legacy-route-v1",
        "legacy_preset_id": "preset.editorial",
        "legacy_template_id": "template.editorial",
        "legacy_copy_tone_profile_id": "copy.direct",
        "new_strategy_id": "strategy.editorial",
        "new_preset_id": "preset.editorial",
        "new_template_id": "template.editorial",
        "new_copy_tone_profile_id": "copy.direct",
        "legacy_family_id": "family.editorial",
        "new_family_id": "family.editorial",
        "preset_match": True,
        "template_match": True,
        "copy_tone_match": True,
        "family_match": True,
        "disagreement_codes": (),
        "comparison_limitations": (),
        "severity": "none",
        "new_route_version": "visual-strategy-route-v3",
        "new_resolver_version": "visual-strategy-resolver-v3",
        "new_registry_version": "visual-strategy-registry-v2",
        "new_registry_snapshot_hash": "registry-hash",
        "canonical_fallback_used": False,
        "canonical_fallback_role": None,
        "canonical_fallback_reason": None,
        "canonical_unsupported_domain": False,
        "canonical_missing_specialized_profile": False,
    }
    payload.update(overrides)
    return payload


@pytest.mark.parametrize(
    "overrides",
    [
        {"preset_match": True, "disagreement_codes": ("preset_mismatch",), "severity": "warning"},
        {"template_match": False, "disagreement_codes": (), "severity": "warning"},
        {"copy_tone_match": None, "legacy_copy_tone_profile_id": "copy.direct"},
        {"copy_tone_match": True, "disagreement_codes": ("copy_tone_mismatch",), "severity": "warning"},
        {"family_match": None, "comparison_limitations": ()},
        {"family_match": True, "comparison_limitations": ("family_metadata_unavailable",)},
        {"family_match": False, "disagreement_codes": (), "severity": "high"},
        {"preset_match": False, "disagreement_codes": ("preset_mismatch",), "severity": "none"},
        {"disagreement_codes": ("preset_mismatch", "preset_mismatch"), "preset_match": False, "severity": "warning"},
        {
            "canonical_fallback_used": False,
            "canonical_fallback_role": "product_editorial",
            "canonical_fallback_reason": "missing_specialized_profile",
        },
        {"canonical_fallback_used": True, "canonical_fallback_role": None, "canonical_fallback_reason": None},
        {
            "canonical_fallback_used": True,
            "canonical_fallback_role": "product_editorial",
            "canonical_fallback_reason": "unknown_reason",
        },
        {
            "canonical_fallback_used": True,
            "canonical_fallback_role": "fallback_role_alpha",
            "canonical_fallback_reason": "unsupported_domain",
            "canonical_unsupported_domain": False,
        },
        {
            "canonical_fallback_used": True,
            "canonical_fallback_role": "fallback_role_alpha",
            "canonical_fallback_reason": "missing_specialized_profile",
            "canonical_missing_specialized_profile": False,
        },
    ],
)
def test_route_comparison_rejects_contradictory_payloads(overrides: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        RouteComparison(**_comparison_payload(**overrides))


def test_route_comparison_rejects_coerced_booleans() -> None:
    with pytest.raises(ValidationError):
        RouteComparison(**_comparison_payload(preset_match="true"))
    with pytest.raises(ValidationError):
        RoutingExecutionPlan(
            mode="shadow",
            run_legacy=1,
            run_canonical=True,
            active_source="legacy",
            canonical_failure_policy="fail_open",
        )


def test_shadow_error_rejects_stage_code_conflict() -> None:
    from orchestrator.app.schemas.visual_routing_shadow import ShadowRoutingError

    with pytest.raises(ValidationError):
        ShadowRoutingError(
            stage="canonical_resolution",
            code="route_comparison_failed",
            exception_type="RuntimeError",
        )


def test_copy_tone_absent_is_unknown_without_mismatch() -> None:
    comparison = compare_visual_routes(
        _legacy_observation(copy_tone_profile_id=None),
        _decision(copy_tone_profile_id="copy.direct"),
        family_resolver=_FamilyResolver({("preset.editorial", "template.editorial"): "family.editorial"}),
    )

    assert comparison.copy_tone_match is None
    assert RouteDisagreementCode.COPY_TONE_MISMATCH not in comparison.disagreement_codes
    assert comparison.severity == RouteComparisonSeverity.NONE


@pytest.mark.parametrize(
    ("legacy", "expected_codes"),
    [
        (
            _legacy_observation(preset_id="preset.old", copy_tone_profile_id="copy.old", route_family_id=None),
            (RouteDisagreementCode.PRESET_MISMATCH, RouteDisagreementCode.COPY_TONE_MISMATCH),
        ),
        (
            _legacy_observation(template_id="template.old", copy_tone_profile_id="copy.old", route_family_id=None),
            (RouteDisagreementCode.TEMPLATE_MISMATCH, RouteDisagreementCode.COPY_TONE_MISMATCH),
        ),
    ],
)
def test_multiple_resource_mismatches_are_high_even_when_family_unavailable(
    legacy: LegacyVisualRouteObservation,
    expected_codes: tuple[RouteDisagreementCode, ...],
) -> None:
    comparison = compare_visual_routes(legacy, _decision(), family_resolver=_FamilyResolver({}))

    assert comparison.disagreement_codes == expected_codes
    assert comparison.comparison_limitations == (RouteComparisonLimitation.FAMILY_METADATA_UNAVAILABLE,)
    assert comparison.severity == RouteComparisonSeverity.HIGH


def test_family_mismatch_with_resource_match_is_high() -> None:
    comparison = compare_visual_routes(
        _legacy_observation(route_family_id="family.old"),
        _decision(),
        family_resolver=_FamilyResolver({("preset.editorial", "template.editorial"): "family.new"}),
    )

    assert comparison.disagreement_codes == (RouteDisagreementCode.FAMILY_MISMATCH,)
    assert comparison.severity == RouteComparisonSeverity.HIGH


def test_custom_comparison_policy_applies_to_resource_mismatch() -> None:
    comparison = compare_visual_routes(
        _legacy_observation(preset_id="preset.old"),
        _decision(),
        family_resolver=_FamilyResolver(
            {
                ("preset.old", "template.editorial"): "family.editorial",
                ("preset.editorial", "template.editorial"): "family.editorial",
            }
        ),
        policy=RouteComparisonPolicy(
            version="custom-policy",
            single_resource_mismatch_severity=RouteComparisonSeverity.INFO,
        ),
    )

    assert comparison.comparison_policy_version == "custom-policy"
    assert comparison.severity == RouteComparisonSeverity.INFO


def test_strategy_id_and_fallback_role_are_independent_dimensions() -> None:
    legacy = _legacy_observation()
    resolver = _FamilyResolver({("preset.editorial", "template.editorial"): "family.editorial"})
    one = compare_visual_routes(legacy, _decision(strategy_id="strategy.one", fallback_used=True), family_resolver=resolver)
    two = compare_visual_routes(legacy, _decision(strategy_id="strategy.two", fallback_used=True), family_resolver=resolver)

    assert one.canonical_fallback_role == "product_editorial"
    assert two.canonical_fallback_role == "product_editorial"
    assert one.severity == two.severity
