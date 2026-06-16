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
        "unsupported_inference_penalty",
        "fallback_penalty",
        "total_score",
    }
    assert set(VisualStrategyDecision.model_fields) == {
        "strategy_id",
        "archetype",
        "composition_template_id",
        "mood_preset_id",
        "copy_tone_profile_id",
        "provider_capabilities",
        "score",
        "fallback_used",
        "fallback_tier",
        "matched_rules",
        "rejected_strategy_ids",
        "registry_version",
        "registry_snapshot_hash",
        "resolver_version",
        "trace",
    }
    assert set(VisualStrategyCandidateTrace.model_fields)
    assert set(VisualStrategyResolutionTrace.model_fields)


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
        unsupported_inference_penalty_weight=0,
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
