from __future__ import annotations

import pytest
from pydantic import ValidationError

from orchestrator.app.llm.campaign_context_service import (
    build_campaign_context,
    campaign_context_from_input_evidence,
)
from orchestrator.app.schemas.campaign_context import CampaignContext
from orchestrator.app.schemas.input_evidence import EvidenceItem, InputEvidenceBundle


def _fact(key: str, value: str) -> EvidenceItem:
    return EvidenceItem(
        key=key,
        value=value,
        source="user_text",
        evidence_class="verified_fact",
        confidence=0.9,
        usable_for_copy=True,
    )


def test_campaign_context_fields_are_exact_contract():
    assert set(CampaignContext.model_fields) == {
        "campaign_intent",
        "campaign_status",
        "promotion_goal",
        "desired_positioning",
        "evidence_refs",
        "confidence",
    }


def test_unknown_empty_campaign_context_is_allowed():
    context = CampaignContext(confidence=0.0)

    assert context.campaign_intent is None
    assert context.campaign_status is None
    assert context.promotion_goal is None
    assert context.desired_positioning == ()
    assert context.evidence_refs == ()


def test_campaign_context_tuple_fields_are_deeply_immutable():
    context = CampaignContext(
        campaign_intent="launch",
        desired_positioning=["premium"],
        evidence_refs=["campaign:e1"],
        confidence=0.8,
    )

    with pytest.raises(AttributeError):
        context.desired_positioning.append("quiet")
    with pytest.raises(AttributeError):
        context.evidence_refs.append("campaign:e2")


@pytest.mark.parametrize(
    "field_name,value",
    [
        ("campaign_intent", 1),
        ("campaign_status", True),
        ("promotion_goal", {"x": "y"}),
        ("desired_positioning", ["premium", 1]),
        ("evidence_refs", [object()]),
    ],
)
def test_campaign_context_rejects_non_string_values(field_name: str, value: object):
    with pytest.raises(ValidationError):
        CampaignContext(confidence=0.8, **{field_name: value})


def test_campaign_context_normalizes_open_vocabulary_without_aliasing():
    context = build_campaign_context(
        campaign_intent=" new_product_launch ",
        campaign_status=" new_menu ",
        promotion_goal=" product_promotion ",
        desired_positioning=[" premium ", "premium", "", "quiet"],
        evidence_refs=[" input:campaign ", "input:campaign", ""],
        confidence=0.9,
    )

    assert context.campaign_intent == "new_product_launch"
    assert context.campaign_status == "new_menu"
    assert context.promotion_goal == "product_promotion"
    assert context.desired_positioning == ("premium", "quiet")
    assert context.evidence_refs == ("input:campaign",)


def test_campaign_claims_require_evidence_refs():
    with pytest.raises(ValidationError, match="campaign context claims require evidence_refs"):
        CampaignContext(campaign_intent="new_product_launch", confidence=0.9)


@pytest.mark.parametrize("confidence", [0.0, 1.0])
def test_campaign_context_allows_confidence_bounds(confidence: float):
    assert CampaignContext(confidence=confidence).confidence == confidence


@pytest.mark.parametrize("confidence", [-0.01, 1.01])
def test_campaign_context_rejects_confidence_out_of_range(confidence: float):
    with pytest.raises(ValidationError):
        CampaignContext(confidence=confidence)


@pytest.mark.parametrize("field_name", ["placement", "visible_copy_mode", "headline_function", "support_function", "campaign_role"])
def test_campaign_context_rejects_downstream_or_format_fields(field_name: str):
    with pytest.raises(ValidationError):
        CampaignContext(confidence=0.8, **{field_name: "not_allowed"})


def test_input_evidence_adapter_projects_campaign_fields_without_placement():
    facts = [
        _fact("campaign_intent", "new_product_launch"),
        _fact("campaign_status", "new_product"),
        _fact("promotion_goal", "product_promotion"),
        _fact("desired_positioning", "premium"),
    ]
    bundle = InputEvidenceBundle(
        input_mode="text_only",
        campaign_intent="new_product_launch",
        campaign_status="new_product",
        promotion_goal="product_promotion",
        desired_positioning=["premium", "premium"],
        placement="poster",
        explicit_user_facts=facts,
        overall_confidence=0.76,
    )

    context = campaign_context_from_input_evidence(bundle)

    assert context.campaign_intent == "new_product_launch"
    assert context.campaign_status == "new_product"
    assert context.promotion_goal == "product_promotion"
    assert context.desired_positioning == ("premium",)
    assert context.evidence_refs == tuple(fact.evidence_id for fact in facts)
    assert not hasattr(context, "placement")


def test_adapter_rejects_partially_grounded_campaign_claims():
    bundle = InputEvidenceBundle(
        input_mode="text_only",
        campaign_intent="new_product_launch",
        campaign_status="new_product",
        explicit_user_facts=[_fact("campaign_intent", "new_product_launch")],
        overall_confidence=0.8,
    )

    with pytest.raises(ValueError, match="campaign_status"):
        campaign_context_from_input_evidence(bundle)


def test_input_evidence_adapter_requires_matching_or_explicit_evidence():
    bundle = InputEvidenceBundle(
        input_mode="text_only",
        campaign_intent="new_product_launch",
        overall_confidence=0.76,
    )

    with pytest.raises(ValueError, match="campaign_intent"):
        campaign_context_from_input_evidence(bundle)

    context = campaign_context_from_input_evidence(bundle, evidence_refs=["input:campaign_intent"])
    assert context.evidence_refs == ("input:campaign_intent",)
