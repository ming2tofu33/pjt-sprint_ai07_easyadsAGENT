from __future__ import annotations

import pytest
from pydantic import ValidationError

from orchestrator.app.schemas.visual_strategy_resolution import (
    VisualStrategyCandidateTrace,
    VisualStrategyDecision,
    VisualStrategyRejectionCode,
    VisualStrategyResolutionTrace,
    VisualStrategyRuntimeContext,
    VisualStrategyScore,
    VisualStrategyScoringPolicy,
)


def test_visual_strategy_resolution_contract_fields():
    assert set(VisualStrategyRuntimeContext.model_fields) == {
        "available_provider_capabilities",
        "campaign_roles",
        "placement",
    }
    assert set(VisualStrategyScore.model_fields) == {
        "evidence_alignment",
        "product_relevance",
        "campaign_fit",
        "format_fit",
        "environment_fit",
        "reference_fit",
        "semantic_fit",
        "unsupported_inference_penalty",
        "fallback_penalty",
        "total_score",
    }
    assert set(VisualStrategyDecision.model_fields) == {
        "strategy_id",
        "route_version",
        "resolver_version",
        "archetype",
        "composition_template_id",
        "mood_preset_id",
        "copy_tone_profile_id",
        "copy_presence_mode",
        "subject_guidance",
        "environment_guidance",
        "negative_constraints",
        "matched_rules",
        "rejected_strategy_ids",
        "eligible_not_selected_strategy_ids",
        "evidence_refs",
        "confidence",
        "provider_capabilities",
        "score",
        "fallback_used",
        "fallback_tier",
        "fallback_role",
        "fallback_reason",
        "unsupported_domain",
        "missing_specialized_profile",
        "registry_version",
        "registry_snapshot_hash",
        "confidence_policy_version",
        "trace",
    }
    assert "fallback_role" in set(VisualStrategyCandidateTrace.model_fields)
    assert {
        "domain_supported_primary_count",
        "eligible_primary_count",
        "eligible_fallback_count",
        "fallback_reason",
        "fallback_role",
        "unsupported_domain",
        "missing_specialized_profile",
    }.issubset(set(VisualStrategyResolutionTrace.model_fields))


def test_runtime_context_normalizes_open_sets_and_rejects_bad_placement():
    runtime = VisualStrategyRuntimeContext(
        available_provider_capabilities=[" capability_alpha ", "capability_alpha"],
        campaign_roles=["role_alpha", ""],
        placement=" poster ",
    )

    assert runtime.available_provider_capabilities == frozenset({"capability_alpha"})
    assert runtime.campaign_roles == frozenset({"role_alpha"})
    assert runtime.placement == "poster"
    with pytest.raises(ValidationError):
        VisualStrategyRuntimeContext(placement=123)


def test_scoring_policy_is_versioned_and_strict():
    policy = VisualStrategyScoringPolicy(
        version="policy-v1",
        evidence_alignment_weight=1,
        product_relevance_weight=0,
        campaign_fit_weight=0,
        format_fit_weight=0,
        environment_fit_weight=0,
        reference_fit_weight=0,
        semantic_fit_weight=0,
        fallback_penalty_weight=0,
        unrestricted_axis_score=0.5,
        fallback_tier_step=0.2,
    )

    assert policy.version == "policy-v1"
    with pytest.raises(ValidationError):
        VisualStrategyScoringPolicy(**{**policy.model_dump(), "version": ""})
    with pytest.raises(ValidationError):
        VisualStrategyScoringPolicy(**{**policy.model_dump(), "evidence_alignment_weight": -1})
    with pytest.raises(ValidationError):
        VisualStrategyScoringPolicy(**{**policy.model_dump(), "unrestricted_axis_score": 1.1})
    with pytest.raises(ValidationError):
        VisualStrategyScoringPolicy(
            **{
                **policy.model_dump(),
                "evidence_alignment_weight": 0,
                "product_relevance_weight": 0,
            }
        )


def test_rejection_codes_are_structural_not_domain_tokens():
    assert VisualStrategyRejectionCode.MISSING_SOURCE_REQUIREMENT.value == "missing_source_requirement"
    assert VisualStrategyRejectionCode.PROHIBITED_VISUAL_ELEMENT.value == "prohibited_visual_element"


def _score(total: float = 1.0) -> VisualStrategyScore:
    return VisualStrategyScore(
        evidence_alignment=1,
        product_relevance=1,
        campaign_fit=1,
        format_fit=1,
        environment_fit=1,
        reference_fit=1,
        semantic_fit=1,
        unsupported_inference_penalty=0,
        fallback_penalty=0,
        total_score=total,
    )


def test_signal_snapshot_fields_separate_fact_and_inference_sources():
    from orchestrator.app.schemas.visual_strategy_resolution import VisualStrategySignalSnapshot

    assert {
        "product_visual_fact_signals",
        "product_visual_inference_signals",
        "semantic_fact_signals",
        "semantic_style_signals",
    }.issubset(set(VisualStrategySignalSnapshot.model_fields))


def test_candidate_trace_state_is_self_consistent():
    score = _score()

    VisualStrategyCandidateTrace(strategy_id="a", eligible=True, score=score)
    VisualStrategyCandidateTrace(strategy_id="b", eligible=False, rejection_codes=(VisualStrategyRejectionCode.DISABLED,))
    with pytest.raises(ValidationError):
        VisualStrategyCandidateTrace(strategy_id="bad", eligible=True, rejection_codes=(VisualStrategyRejectionCode.DISABLED,), score=score)
    with pytest.raises(ValidationError):
        VisualStrategyCandidateTrace(strategy_id="bad", eligible=False)
    with pytest.raises(ValidationError):
        VisualStrategyCandidateTrace(strategy_id="bad", eligible=True, missing_required_tags=frozenset({"x"}), score=score)
    with pytest.raises(ValidationError):
        VisualStrategyCandidateTrace(strategy_id="bad", eligible=True, blocked_visual_elements=frozenset({"x"}), score=score)


def test_resolution_trace_counts_are_self_consistent():
    candidate = VisualStrategyCandidateTrace(strategy_id="a", eligible=True, score=_score())

    VisualStrategyResolutionTrace(
        resolver_version="resolver",
        scoring_policy_version="policy",
        registry_version="registry",
        registry_snapshot_hash="hash",
        candidate_count=1,
        eligible_count=1,
        non_fallback_eligible_count=1,
        fallback_eligible_count=0,
        selected_strategy_id="a",
        fallback_used=False,
        candidates=(candidate,),
    )
    with pytest.raises(ValidationError):
        VisualStrategyResolutionTrace(
            resolver_version="resolver",
            scoring_policy_version="policy",
            registry_version="registry",
            registry_snapshot_hash="hash",
            candidate_count=2,
            eligible_count=1,
            non_fallback_eligible_count=1,
            fallback_eligible_count=0,
            selected_strategy_id="a",
            fallback_used=False,
            candidates=(candidate,),
        )
    with pytest.raises(ValidationError):
        VisualStrategyResolutionTrace(
            resolver_version="resolver",
            scoring_policy_version="policy",
            registry_version="registry",
            registry_snapshot_hash="hash",
            candidate_count=2,
            eligible_count=2,
            non_fallback_eligible_count=2,
            fallback_eligible_count=0,
            selected_strategy_id="a",
            fallback_used=False,
            candidates=(candidate, candidate),
        )
    with pytest.raises(ValidationError):
        VisualStrategyResolutionTrace(
            resolver_version="resolver",
            scoring_policy_version="policy",
            registry_version="registry",
            registry_snapshot_hash="hash",
            candidate_count=1,
            eligible_count=1,
            non_fallback_eligible_count=1,
            fallback_eligible_count=0,
            selected_strategy_id=None,
            fallback_used=False,
            candidates=(candidate,),
        )


def test_decision_must_match_selected_trace_candidate():
    score = _score(0.7)
    candidate = VisualStrategyCandidateTrace(strategy_id="selected", eligible=True, score=score)
    trace = VisualStrategyResolutionTrace(
        resolver_version="resolver",
        scoring_policy_version="policy",
        registry_version="registry",
        registry_snapshot_hash="hash",
        candidate_count=1,
        eligible_count=1,
        non_fallback_eligible_count=1,
        fallback_eligible_count=0,
        selected_strategy_id="selected",
        fallback_used=False,
        candidates=(candidate,),
    )

    VisualStrategyDecision(
        strategy_id="selected",
        route_version="route",
        resolver_version="resolver",
        archetype="archetype",
        composition_template_id="template",
        mood_preset_id="preset",
        copy_tone_profile_id="tone",
        copy_presence_mode="copy_optional",
        subject_guidance=(),
        environment_guidance=(),
        negative_constraints=(),
        matched_rules=(),
        rejected_strategy_ids=(),
        eligible_not_selected_strategy_ids=(),
        evidence_refs=(),
        confidence=0.7,
        provider_capabilities=frozenset(),
        score=score,
        fallback_used=False,
        fallback_tier=0,
        fallback_reason=None,
        registry_version="registry",
        registry_snapshot_hash="hash",
        confidence_policy_version="confidence-policy",
        trace=trace,
    )
    with pytest.raises(ValidationError):
        VisualStrategyDecision(
            strategy_id="different",
            route_version="route",
            resolver_version="resolver",
            archetype="archetype",
            composition_template_id="template",
            mood_preset_id="preset",
            copy_tone_profile_id="tone",
            copy_presence_mode="copy_optional",
            subject_guidance=(),
            environment_guidance=(),
            negative_constraints=(),
            matched_rules=(),
            rejected_strategy_ids=(),
            eligible_not_selected_strategy_ids=(),
            evidence_refs=(),
            confidence=0.7,
            provider_capabilities=frozenset(),
            score=score,
            fallback_used=False,
            fallback_tier=0,
            fallback_reason=None,
            registry_version="registry",
            registry_snapshot_hash="hash",
            confidence_policy_version="confidence-policy",
            trace=trace,
        )


def test_decision_rejected_id_lists_must_match_trace():
    score = _score()
    selected = VisualStrategyCandidateTrace(strategy_id="selected", eligible=True, score=score)
    rejected = VisualStrategyCandidateTrace(strategy_id="rejected", eligible=False, rejection_codes=(VisualStrategyRejectionCode.DISABLED,))
    trace = VisualStrategyResolutionTrace(
        resolver_version="resolver",
        scoring_policy_version="policy",
        registry_version="registry",
        registry_snapshot_hash="hash",
        candidate_count=2,
        eligible_count=1,
        non_fallback_eligible_count=1,
        fallback_eligible_count=0,
        selected_strategy_id="selected",
        fallback_used=False,
        candidates=(selected, rejected),
    )
    payload = {
        "strategy_id": "selected",
        "route_version": "route",
        "resolver_version": "resolver",
        "archetype": "archetype",
        "composition_template_id": "template",
        "mood_preset_id": "preset",
        "copy_tone_profile_id": "tone",
        "copy_presence_mode": "copy_optional",
        "subject_guidance": (),
        "environment_guidance": (),
        "negative_constraints": (),
        "matched_rules": (),
        "rejected_strategy_ids": ("rejected",),
        "eligible_not_selected_strategy_ids": (),
        "evidence_refs": (),
        "confidence": 0.7,
        "provider_capabilities": frozenset(),
        "score": score,
        "fallback_used": False,
        "fallback_tier": 0,
        "fallback_reason": None,
        "registry_version": "registry",
        "registry_snapshot_hash": "hash",
        "confidence_policy_version": "confidence-policy",
        "trace": trace,
    }
    VisualStrategyDecision(**payload)
    with pytest.raises(ValidationError):
        VisualStrategyDecision(**{**payload, "rejected_strategy_ids": ()})


@pytest.mark.parametrize(
    "field_name",
    [
        "strategy_id",
        "archetype",
        "composition_template_id",
        "mood_preset_id",
        "copy_tone_profile_id",
        "registry_version",
        "registry_snapshot_hash",
    ],
)
def test_decision_id_fields_are_strict_non_empty(field_name: str):
    score = _score()
    candidate = VisualStrategyCandidateTrace(strategy_id="selected", eligible=True, score=score)
    trace = VisualStrategyResolutionTrace(
        resolver_version="resolver",
        scoring_policy_version="policy",
        registry_version="registry",
        registry_snapshot_hash="hash",
        candidate_count=1,
        eligible_count=1,
        non_fallback_eligible_count=1,
        fallback_eligible_count=0,
        selected_strategy_id="selected",
        fallback_used=False,
        candidates=(candidate,),
    )
    payload = {
        "strategy_id": "selected",
        "route_version": "route",
        "resolver_version": "resolver",
        "archetype": "archetype",
        "composition_template_id": "template",
        "mood_preset_id": "preset",
        "copy_tone_profile_id": "tone",
        "copy_presence_mode": "copy_optional",
        "subject_guidance": (),
        "environment_guidance": (),
        "negative_constraints": (),
        "matched_rules": (),
        "rejected_strategy_ids": (),
        "eligible_not_selected_strategy_ids": (),
        "evidence_refs": (),
        "confidence": 0.7,
        "provider_capabilities": frozenset(),
        "score": score,
        "fallback_used": False,
        "fallback_tier": 0,
        "fallback_reason": None,
        "registry_version": "registry",
        "registry_snapshot_hash": "hash",
        "confidence_policy_version": "confidence-policy",
        "trace": trace,
    }
    with pytest.raises(ValidationError):
        VisualStrategyDecision(**{**payload, field_name: ""})
