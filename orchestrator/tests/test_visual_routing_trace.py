from __future__ import annotations

import json

import pytest
from pydantic import TypeAdapter, ValidationError

from orchestrator.app.llm.ad_format_presets import build_ad_format_spec
from orchestrator.app.llm.creative_routing_context_service import build_creative_routing_context
from orchestrator.app.llm.domain_routing import CanonicalBusinessDomain, DomainRoutingResult, DomainSupportStatus, LegacyVisualRouteKey
from orchestrator.app.llm.visual_routing_shadow import VisualRoutingModeExecution, compare_visual_routes
from orchestrator.app.llm.visual_routing_trace import (
    VisualRoutingTraceBuildError,
    build_registry_stage_observation,
    build_visual_routing_trace,
    summarize_visual_strategy_decision,
)
from orchestrator.app.schemas.business_context import BusinessEnvironmentContext
from orchestrator.app.schemas.campaign_context import CampaignContext
from orchestrator.app.schemas.creative_routing import CreativeRoutingContext
from orchestrator.app.schemas.input_evidence import EvidenceItem, InputConflict
from orchestrator.app.schemas.product_understanding import ProductUnderstanding
from orchestrator.app.schemas.product_visual_context import ProductVisualContext
from orchestrator.app.schemas.visual_routing_shadow import (
    LegacyVisualRouteObservation,
    RoutingMode,
    RoutingSource,
    ShadowRoutingError,
    ShadowRoutingErrorCode,
    ShadowRoutingErrorStage,
)
from orchestrator.app.schemas.visual_routing_trace import (
    VISUAL_ROUTING_TRACE_VERSION,
    CanonicalVisualRoutingTrace,
    LegacyVisualRoutingTrace,
    ShadowVisualRoutingTrace,
    VisualRoutingDiagnosticStage,
    VisualRoutingInputSnapshot,
    VisualRoutingStageObservation,
    VisualRoutingStageStatus,
    VisualRoutingTrace,
    VisualRoutingTraceCompleteness,
)
from orchestrator.app.schemas.visual_strategy_resolution import (
    VisualStrategyCandidateTrace,
    VisualStrategyDecision,
    VisualStrategyFallbackReason,
    VisualStrategyResolutionTrace,
    VisualStrategyScore,
)
from orchestrator.app.schemas.visual_strategy_integrity import (
    DiscriminatedUnionAuditStatus,
    RegistryValidationCode,
    RegistryValidationIssue,
    RegistryValidationReport,
    RegistryValidationSeverity,
)


def _score(total: float = 0.9) -> VisualStrategyScore:
    return VisualStrategyScore(
        evidence_alignment=1.0,
        product_relevance=1.0,
        campaign_fit=1.0,
        format_fit=1.0,
        environment_fit=1.0,
        reference_fit=1.0,
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
        matched_evidence_refs=("semantic:e1",),
        score=score,
    )
    trace = VisualStrategyResolutionTrace(
        resolver_version="visual-strategy-resolver-v2",
        scoring_policy_version="visual-strategy-scoring-v1",
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
        route_version="visual-strategy-route-v2",
        resolver_version="visual-strategy-resolver-v2",
        archetype="editorial",
        composition_template_id=template_id,
        mood_preset_id=preset_id,
        copy_tone_profile_id=copy_tone_profile_id,
        copy_presence_mode="optional",
        subject_guidance=("show product",),
        environment_guidance=("simple surface",),
        negative_constraints=("no unsupported claim",),
        matched_rules=("rule.one", " rule.one ", "rule.two"),
        rejected_strategy_ids=(),
        eligible_not_selected_strategy_ids=(),
        evidence_refs=("semantic:e1",),
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
    preset_id: str = "preset.legacy",
    template_id: str = "template.legacy",
    copy_tone_profile_id: str | None = "copy.legacy",
) -> LegacyVisualRouteObservation:
    return LegacyVisualRouteObservation(
        legacy_route_key=LegacyVisualRouteKey.GENERIC,
        preset_id=preset_id,
        template_id=template_id,
        copy_tone_profile_id=copy_tone_profile_id,
        route_family_id="family.legacy",
        route_version="legacy-route-v1",
    )


def _context() -> CreativeRoutingContext:
    domain = DomainRoutingResult(
        raw_business_type="retail",
        canonical_domain=CanonicalBusinessDomain.RETAIL,
        support_status=DomainSupportStatus.SPECIALIZED,
        confidence=0.9,
        evidence_refs=["domain:e1"],
    )
    product = ProductUnderstanding(
        product_name="desk lamp",
        broad_category="home_and_living",
        category_path=["home_and_living", "lighting", "desk_lamp"],
        product_name_evidence_ids=["product:name"],
        verified_facts=[
            EvidenceItem(
                evidence_id="product:fact",
                key="product_name",
                value="desk lamp",
                source="user_text",
                evidence_class="verified_fact",
                confidence=0.9,
                usable_for_copy=True,
            )
        ],
        confidence=0.86,
    )
    return build_creative_routing_context(
        domain=domain,
        business=BusinessEnvironmentContext(
            broad_domain=CanonicalBusinessDomain.RETAIL,
            business_tags=[" retail_tag ", "retail_tag", ""],
            evidence_refs=["business:e1"],
            confidence=0.8,
        ),
        product=product,
        product_visual=ProductVisualContext(
            product_name="desk lamp",
            category_path=["home_and_living", "lighting", "desk_lamp"],
            product_tags=["lamp", "lamp", "brass"],
            evidence_refs=["product_visual:e1"],
            confidence=0.84,
        ),
        campaign=CampaignContext(
            campaign_intent="product_promotion",
            evidence_refs=["campaign:e1"],
            confidence=0.7,
        ),
        ad_format=build_ad_format_spec("poster"),
        ambiguity_flags=["ambiguous_category", " ambiguous_category ", ""],
        input_conflicts=[
            InputConflict(
                conflict_id="conflict:one",
                field="product",
                left_value="a",
                text_value="a",
                image_value="b",
                conflict_type="identity_mismatch",
                severity="warning",
                confidence=0.6,
                recommended_resolution="manual_review",
            )
        ],
        resolver_version="visual-strategy-resolver-v2",
    )


def _stage(
    stage: VisualRoutingDiagnosticStage,
    status: VisualRoutingStageStatus = VisualRoutingStageStatus.SUCCEEDED,
    *,
    codes: tuple[str, ...] = (),
    error_type: str | None = None,
    artifacts: tuple[str, ...] = (),
) -> VisualRoutingStageObservation:
    return VisualRoutingStageObservation(
        stage=stage,
        status=status,
        diagnostic_codes=codes,
        artifact_refs=artifacts,
        error_type=error_type,
    )


def test_trace_union_parses_variants_rejects_unknown_extra_and_roundtrips() -> None:
    trace = build_visual_routing_trace(
        execution=VisualRoutingModeExecution(mode=RoutingMode.LEGACY, active_source=RoutingSource.LEGACY, legacy_result="legacy"),
        context=_context(),
        raw_business_type="retail",
        legacy_observation=_legacy_observation(),
    )
    adapter = TypeAdapter(VisualRoutingTrace)

    parsed = adapter.validate_json(trace.model_dump_json())
    assert isinstance(parsed, LegacyVisualRoutingTrace)
    assert parsed == trace
    with pytest.raises(ValidationError):
        adapter.validate_python({**trace.model_dump(mode="json"), "routing_mode": "unknown"})
    with pytest.raises(ValidationError):
        LegacyVisualRoutingTrace(**trace.model_dump(), extra_field=True)
    with pytest.raises(ValidationError):
        trace.completeness = VisualRoutingTraceCompleteness.PARTIAL


def test_input_snapshot_sanitizes_and_deduplicates_without_prompt_payloads() -> None:
    trace = build_visual_routing_trace(
        execution=VisualRoutingModeExecution(mode=RoutingMode.LEGACY, active_source=RoutingSource.LEGACY, legacy_result="legacy"),
        context=_context(),
        raw_business_type="retail",
        campaign_roles=["hero", " hero ", "", "secondary"],
        placement="poster",
        legacy_observation=_legacy_observation(),
        additional_evidence_refs=["domain:e1", "extra:e1"],
    )

    assert trace.input_snapshot.product_name == "desk lamp"
    assert trace.input_snapshot.product_category_path == ("home_and_living", "lighting", "desk_lamp")
    assert trace.input_snapshot.product_visual_category_path == ("home_and_living", "lighting", "desk_lamp")
    assert trace.input_snapshot.category_path_match is True
    assert trace.input_snapshot.business_tags == ("retail_tag",)
    assert trace.input_snapshot.product_tags == ("lamp", "brass")
    assert trace.input_snapshot.campaign_roles == ("hero", "secondary")
    assert trace.input_snapshot.ambiguity_flags == ("ambiguous_category",)
    assert trace.input_snapshot.input_conflict_ids == ("conflict:one",)
    assert trace.input_snapshot.input_conflict_types == ("identity_mismatch",)
    assert trace.input_snapshot.evidence_refs == (
        "domain:e1",
        "business:e1",
        "product:name",
        "product:fact",
        "product_visual:e1",
        "campaign:e1",
        "extra:e1",
    )
    assert "secret-user-prompt" not in trace.model_dump_json()


def test_legacy_trace_requires_observation_and_uses_legacy_active_route() -> None:
    legacy = _legacy_observation()
    trace = build_visual_routing_trace(
        execution=VisualRoutingModeExecution(mode=RoutingMode.LEGACY, active_source=RoutingSource.LEGACY, legacy_result="legacy"),
        context=_context(),
        raw_business_type="retail",
        legacy_observation=legacy,
    )

    assert trace.routing_mode == RoutingMode.LEGACY
    assert trace.canonical_decision is None
    assert trace.route_disagreement is None
    assert trace.shadow_error is None
    assert trace.active_route.source == RoutingSource.LEGACY
    assert trace.active_route.strategy_id is None
    assert trace.active_route.template_id == legacy.template_id
    assert trace.completeness == VisualRoutingTraceCompleteness.COMPLETE

    with pytest.raises(VisualRoutingTraceBuildError, match="legacy observation"):
        build_visual_routing_trace(
            execution=VisualRoutingModeExecution(mode=RoutingMode.LEGACY, active_source=RoutingSource.LEGACY, legacy_result="legacy"),
            context=_context(),
            raw_business_type="retail",
        )


def test_shadow_success_trace_keeps_legacy_active_and_canonical_observational() -> None:
    legacy = _legacy_observation()
    canonical = _decision()
    comparison = compare_visual_routes(legacy, canonical)
    execution = VisualRoutingModeExecution(
        mode=RoutingMode.SHADOW,
        active_source=RoutingSource.LEGACY,
        legacy_result="legacy",
        legacy_observation=legacy,
        canonical_decision=canonical,
        comparison=comparison,
    )

    trace = build_visual_routing_trace(execution=execution, context=_context(), raw_business_type="retail")

    assert isinstance(trace, ShadowVisualRoutingTrace)
    assert trace.completeness == VisualRoutingTraceCompleteness.COMPLETE
    assert trace.active_route.source == RoutingSource.LEGACY
    assert trace.active_route.template_id == legacy.template_id
    assert trace.canonical_decision is not None
    assert trace.canonical_decision.strategy_id == canonical.strategy_id
    assert trace.route_disagreement is comparison
    assert trace.shadow_error is None


def test_shadow_failure_trace_is_partial_and_sanitized() -> None:
    legacy = _legacy_observation()
    error = ShadowRoutingError(
        stage=ShadowRoutingErrorStage.CANONICAL_RESOLUTION,
        code=ShadowRoutingErrorCode.CANONICAL_RESOLUTION_FAILED,
        exception_type="RuntimeError",
    )
    trace = build_visual_routing_trace(
        execution=VisualRoutingModeExecution(
            mode=RoutingMode.SHADOW,
            active_source=RoutingSource.LEGACY,
            legacy_result="legacy",
            legacy_observation=legacy,
            shadow_error=error,
        ),
        context=_context(),
        raw_business_type="retail",
    )

    assert trace.completeness == VisualRoutingTraceCompleteness.PARTIAL
    assert trace.canonical_decision is None
    assert trace.route_disagreement is None
    assert trace.shadow_error is error
    assert trace.stage_observations[0].stage == VisualRoutingDiagnosticStage.STRATEGY_RESOLUTION
    assert "provider-secret" not in trace.model_dump_json()


def test_canonical_trace_uses_canonical_active_route() -> None:
    canonical = _decision()
    trace = build_visual_routing_trace(
        execution=VisualRoutingModeExecution(
            mode=RoutingMode.CANONICAL,
            active_source=RoutingSource.CANONICAL,
            canonical_decision=canonical,
        ),
        context=_context(),
        raw_business_type="retail",
    )

    assert isinstance(trace, CanonicalVisualRoutingTrace)
    assert trace.legacy_observation is None
    assert trace.route_disagreement is None
    assert trace.active_route.source == RoutingSource.CANONICAL
    assert trace.active_route.strategy_id == canonical.strategy_id
    assert trace.active_route.template_id == canonical.composition_template_id
    assert trace.completeness == VisualRoutingTraceCompleteness.COMPLETE


def test_stage_observation_contract_and_ordering() -> None:
    trace = build_visual_routing_trace(
        execution=VisualRoutingModeExecution(mode=RoutingMode.LEGACY, active_source=RoutingSource.LEGACY, legacy_result="legacy"),
        context=_context(),
        raw_business_type="retail",
        legacy_observation=_legacy_observation(),
        stage_observations=[
            _stage(VisualRoutingDiagnosticStage.IMAGE_GENERATION, VisualRoutingStageStatus.DEGRADED, codes=("quality_report_mismatch",), artifacts=("quality:1",)),
            _stage(VisualRoutingDiagnosticStage.PRODUCT_UNDERSTANDING),
        ],
    )

    assert [item.stage for item in trace.stage_observations] == [
        VisualRoutingDiagnosticStage.PRODUCT_UNDERSTANDING,
        VisualRoutingDiagnosticStage.IMAGE_GENERATION,
    ]
    with pytest.raises(ValidationError):
        VisualRoutingStageObservation(stage="strategy_resolution", status="failed")
    with pytest.raises(ValidationError):
        VisualRoutingStageObservation(stage="strategy_resolution", status="degraded")
    with pytest.raises(ValidationError):
        LegacyVisualRoutingTrace(**{**trace.model_dump(), "stage_observations": [*_stage_duplicate(trace)]})

    adapter = TypeAdapter(VisualRoutingTrace)
    assert adapter.validate_json(trace.model_dump_json()) == trace


def _stage_duplicate(trace: LegacyVisualRoutingTrace) -> tuple[VisualRoutingStageObservation, VisualRoutingStageObservation]:
    return (trace.stage_observations[0], trace.stage_observations[0])


def test_shadow_legacy_observation_failure_allows_partial_trace_without_active_route() -> None:
    error = ShadowRoutingError(
        stage=ShadowRoutingErrorStage.LEGACY_OBSERVATION,
        code=ShadowRoutingErrorCode.LEGACY_OBSERVATION_FAILED,
        exception_type="RuntimeError",
    )
    trace = build_visual_routing_trace(
        execution=VisualRoutingModeExecution(
            mode=RoutingMode.SHADOW,
            active_source=RoutingSource.LEGACY,
            legacy_result="legacy",
            canonical_decision=_decision(),
            shadow_error=error,
        ),
        context=_context(),
        raw_business_type="retail",
    )

    assert trace.completeness == VisualRoutingTraceCompleteness.PARTIAL
    assert trace.active_route is None
    assert trace.legacy_observation is None
    assert trace.route_disagreement is None
    assert trace.shadow_error is error


def test_shadow_error_stage_upsert_avoids_duplicate_stage() -> None:
    legacy = _legacy_observation()
    error = ShadowRoutingError(
        stage=ShadowRoutingErrorStage.CANONICAL_RESOLUTION,
        code=ShadowRoutingErrorCode.CANONICAL_RESOLUTION_FAILED,
        exception_type="RuntimeError",
    )
    trace = build_visual_routing_trace(
        execution=VisualRoutingModeExecution(
            mode=RoutingMode.SHADOW,
            active_source=RoutingSource.LEGACY,
            legacy_result="legacy",
            legacy_observation=legacy,
            shadow_error=error,
        ),
        context=_context(),
        raw_business_type="retail",
        stage_observations=[
            _stage(VisualRoutingDiagnosticStage.STRATEGY_RESOLUTION, VisualRoutingStageStatus.DEGRADED, codes=("fallback_used",))
        ],
    )

    assert [item.stage for item in trace.stage_observations].count(VisualRoutingDiagnosticStage.STRATEGY_RESOLUTION) == 1
    assert trace.stage_observations[0].diagnostic_codes == ("fallback_used", "canonical_resolution_failed")


def test_source_conflicts_are_build_errors() -> None:
    with pytest.raises(VisualRoutingTraceBuildError, match="placement"):
        build_visual_routing_trace(
            execution=VisualRoutingModeExecution(mode=RoutingMode.LEGACY, active_source=RoutingSource.LEGACY, legacy_result="legacy"),
            context=_context(),
            raw_business_type="retail",
            placement="feed",
            legacy_observation=_legacy_observation(),
        )

    with pytest.raises(VisualRoutingTraceBuildError, match="raw business type"):
        build_visual_routing_trace(
            execution=VisualRoutingModeExecution(mode=RoutingMode.LEGACY, active_source=RoutingSource.LEGACY, legacy_result="legacy"),
            context=_context(),
            raw_business_type="beauty",
            legacy_observation=_legacy_observation(),
        )

    with pytest.raises(VisualRoutingTraceBuildError, match="legacy observation"):
        build_visual_routing_trace(
            execution=VisualRoutingModeExecution(
                mode=RoutingMode.LEGACY,
                active_source=RoutingSource.LEGACY,
                legacy_result="legacy",
                legacy_observation=_legacy_observation(preset_id="preset.execution"),
            ),
            context=_context(),
            raw_business_type="retail",
            legacy_observation=_legacy_observation(preset_id="preset.explicit"),
        )


def test_category_path_mismatch_is_recorded_not_silently_overwritten() -> None:
    context = _context().model_copy(
        update={
            "product_visual": ProductVisualContext(
                product_name="desk lamp",
                category_path=["home_and_living", "decor"],
                product_tags=["lamp"],
                evidence_refs=["product_visual:e1"],
                confidence=0.84,
            )
        }
    )
    trace = build_visual_routing_trace(
        execution=VisualRoutingModeExecution(mode=RoutingMode.LEGACY, active_source=RoutingSource.LEGACY, legacy_result="legacy"),
        context=context,
        raw_business_type="retail",
        legacy_observation=_legacy_observation(),
    )

    assert trace.input_snapshot.product_category_path == ("home_and_living", "lighting", "desk_lamp")
    assert trace.input_snapshot.product_visual_category_path == ("home_and_living", "decor")
    assert trace.input_snapshot.category_path_match is False


@pytest.mark.parametrize(
    "raw_business_type",
    ["retail\nfull prompt", "x" * 81],
)
def test_raw_business_type_rejects_long_or_multiline_values(raw_business_type: str) -> None:
    with pytest.raises(ValidationError):
        VisualRoutingInputSnapshot(
            raw_business_type=raw_business_type,
            canonical_domain=CanonicalBusinessDomain.RETAIL,
            product_name="desk lamp",
            category_path_match=True,
        )


@pytest.mark.parametrize(
    "artifact_ref",
    ["https://signed-url.example/a", r"C:\private\file.png", "bucket/object_key", "base64payload"],
)
def test_artifact_refs_reject_url_path_object_key_and_payload_markers(artifact_ref: str) -> None:
    with pytest.raises(ValidationError):
        VisualRoutingStageObservation(
            stage=VisualRoutingDiagnosticStage.IMAGE_GENERATION,
            status=VisualRoutingStageStatus.DEGRADED,
            diagnostic_codes=("quality_report",),
            artifact_refs=(artifact_ref,),
        )


def test_error_type_rejects_exception_message_shape() -> None:
    with pytest.raises(ValidationError):
        VisualRoutingStageObservation(
            stage=VisualRoutingDiagnosticStage.PROVIDER_PROMPT_ADAPTER,
            status=VisualRoutingStageStatus.FAILED,
            diagnostic_codes=("adapter_failed",),
            error_type="RuntimeError: provider-secret",
        )


def test_canonical_summary_rejects_fallback_contradictions() -> None:
    summary = summarize_visual_strategy_decision(_decision())
    with pytest.raises(ValidationError):
        type(summary)(**(summary.model_dump() | {"fallback_used": False, "fallback_role": "product_editorial"}))
    with pytest.raises(ValidationError):
        type(summary)(**(summary.model_dump() | {"unsupported_domain": True, "missing_specialized_profile": True}))


def test_shadow_legacy_active_route_rejects_strategy_id() -> None:
    legacy = _legacy_observation()
    trace = build_visual_routing_trace(
        execution=VisualRoutingModeExecution(mode=RoutingMode.LEGACY, active_source=RoutingSource.LEGACY, legacy_result="legacy"),
        context=_context(),
        raw_business_type="retail",
        legacy_observation=legacy,
    )
    payload = trace.model_dump()
    payload["routing_mode"] = RoutingMode.SHADOW
    payload["completeness"] = VisualRoutingTraceCompleteness.PARTIAL
    payload["legacy_observation"] = legacy
    payload["active_route"] = payload["active_route"] | {"strategy_id": "strategy.canonical"}
    payload["shadow_error"] = ShadowRoutingError(
        stage=ShadowRoutingErrorStage.LEGACY_OBSERVATION,
        code=ShadowRoutingErrorCode.LEGACY_OBSERVATION_FAILED,
        exception_type="RuntimeError",
    )

    with pytest.raises(ValidationError):
        ShadowVisualRoutingTrace(**payload)


def test_comparison_canonical_mismatch_is_build_error() -> None:
    legacy = _legacy_observation()
    canonical = _decision()
    other = _decision(strategy_id="strategy.other")
    comparison = compare_visual_routes(legacy, other)

    with pytest.raises(ValidationError, match="comparison strategy"):
        build_visual_routing_trace(
            execution=VisualRoutingModeExecution(
                mode=RoutingMode.SHADOW,
                active_source=RoutingSource.LEGACY,
                legacy_result="legacy",
                legacy_observation=legacy,
                canonical_decision=canonical,
                comparison=comparison,
            ),
            context=_context(),
            raw_business_type="retail",
        )


def test_summary_projection_and_fallback_metadata_are_exact() -> None:
    decision = _decision(fallback_used=True)
    summary = summarize_visual_strategy_decision(decision)

    assert summary.strategy_id == decision.strategy_id
    assert summary.template_id == decision.composition_template_id
    assert summary.preset_id == decision.mood_preset_id
    assert summary.fallback_role == "product_editorial"
    assert summary.fallback_reason == VisualStrategyFallbackReason.MISSING_SPECIALIZED_PROFILE
    assert summary.total_score == decision.score.total_score
    assert summary.matched_rules == ("rule.one", "rule.two")


def test_no_automatic_hallucination_stage_from_high_route_disagreement() -> None:
    legacy = _legacy_observation()
    canonical = _decision(preset_id="preset.new", template_id="template.new")
    comparison = compare_visual_routes(legacy, canonical)
    trace = build_visual_routing_trace(
        execution=VisualRoutingModeExecution(
            mode=RoutingMode.SHADOW,
            active_source=RoutingSource.LEGACY,
            legacy_result="legacy",
            legacy_observation=legacy,
            canonical_decision=canonical,
            comparison=comparison,
        ),
        context=_context(),
        raw_business_type="retail",
    )

    assert comparison.severity.value == "high"
    assert VisualRoutingDiagnosticStage.IMAGE_GENERATION not in {item.stage for item in trace.stage_observations}


def test_deterministic_json_serialization() -> None:
    kwargs = {
        "execution": VisualRoutingModeExecution(mode=RoutingMode.LEGACY, active_source=RoutingSource.LEGACY, legacy_result="legacy"),
        "context": _context(),
        "raw_business_type": "retail",
        "legacy_observation": _legacy_observation(),
        "campaign_roles": ["a", "b", "a"],
    }
    first = build_visual_routing_trace(**kwargs)
    second = build_visual_routing_trace(**kwargs)

    assert first.model_dump_json() == second.model_dump_json()
    assert json.loads(first.model_dump_json()) == json.loads(second.model_dump_json())


def test_payload_leak_terms_are_not_trace_fields_or_values() -> None:
    trace = build_visual_routing_trace(
        execution=VisualRoutingModeExecution(mode=RoutingMode.LEGACY, active_source=RoutingSource.LEGACY, legacy_result="secret-user-prompt"),
        context=_context(),
        raw_business_type="retail",
        legacy_observation=_legacy_observation(),
        stage_observations=[
            VisualRoutingStageObservation(
                stage=VisualRoutingDiagnosticStage.PROVIDER_PROMPT_ADAPTER,
                status=VisualRoutingStageStatus.FAILED,
                diagnostic_codes=("adapter_failed",),
                error_type="ProviderAdapterError",
            )
        ],
    )

    dumped = trace.model_dump_json()
    assert "secret-user-prompt" not in dumped
    assert "provider-secret" not in dumped
    assert "local-object-key" not in dumped
    assert "traceback" not in dumped


def _registry_report(*, valid: bool, complete: bool, issues: tuple[RegistryValidationIssue, ...] = ()) -> RegistryValidationReport:
    return RegistryValidationReport(
        validator_version="visual-strategy-integrity-validator-v1",
        registry_version="visual-strategy-registry-v2",
        registry_snapshot_hash="registry-hash",
        profile_count=1,
        enabled_profile_count=1,
        disabled_profile_count=0,
        fallback_profile_count=0,
        enabled_fallback_profile_count=0,
        error_count=sum(1 for issue in issues if issue.severity == RegistryValidationSeverity.ERROR),
        warning_count=sum(1 for issue in issues if issue.severity == RegistryValidationSeverity.WARNING),
        info_count=sum(1 for issue in issues if issue.severity == RegistryValidationSeverity.INFO),
        valid=valid,
        complete=complete,
        issues=issues,
        checked_composition_template_count=1,
        checked_mood_preset_count=1,
        checked_copy_tone_profile_count=1,
        checked_provider_capability_count=1,
        archetype_validation_mode="catalog",
        provider_capability_validation_mode="catalog",
        snapshot_hash_validation_mode="strict",
        discriminated_union_status=DiscriminatedUnionAuditStatus.APPLIED,
    )


def test_registry_stage_adapter_maps_valid_incomplete_and_invalid_reports() -> None:
    assert build_registry_stage_observation(_registry_report(valid=True, complete=True)).status == VisualRoutingStageStatus.SUCCEEDED
    assert build_registry_stage_observation(_registry_report(valid=True, complete=False)).status == VisualRoutingStageStatus.UNAVAILABLE

    issue = RegistryValidationIssue(
        code=RegistryValidationCode.MISSING_MOOD_PRESET,
        severity=RegistryValidationSeverity.ERROR,
        message="missing preset",
    )
    failed = build_registry_stage_observation(_registry_report(valid=False, complete=False, issues=(issue,)))
    assert failed.status == VisualRoutingStageStatus.FAILED
    assert failed.diagnostic_codes == ("missing_mood_preset",)
    assert failed.error_type == "RegistryValidationError"
