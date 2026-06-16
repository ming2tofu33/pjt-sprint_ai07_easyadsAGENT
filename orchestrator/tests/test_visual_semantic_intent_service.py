from __future__ import annotations

import asyncio

import pytest

from orchestrator.app.llm.ad_format_presets import build_ad_format_spec
from orchestrator.app.llm.creative_routing_context_service import build_creative_routing_context
from orchestrator.app.llm.domain_routing import CanonicalBusinessDomain, DomainRoutingResult, DomainSupportStatus
from orchestrator.app.llm.visual_semantic_intent_service import (
    SYSTEM_INSTRUCTION,
    VisualSemanticIntentGroundingError,
    VisualSemanticIntentIdentifierLeakError,
    VisualSemanticIntentValidationError,
    VisualSemanticIntentValidationPolicy,
    build_semantic_grounding_snapshot,
    build_visual_semantic_input_projection,
    generate_visual_semantic_intent,
)
from orchestrator.app.schemas.business_context import BusinessEnvironmentContext
from orchestrator.app.schemas.campaign_context import CampaignContext
from orchestrator.app.schemas.creative_routing import CreativeRoutingContext
from orchestrator.app.schemas.input_evidence import EvidenceItem, InputConflict
from orchestrator.app.schemas.product_understanding import ProductUnderstanding
from orchestrator.app.schemas.product_visual_context import ProductVisualContext
from orchestrator.app.schemas.visual_semantic_intent import (
    SemanticIntentAttribution,
    VisualSemanticIntent,
    VisualSemanticIntentDraft,
)


class FakeStructuredSemanticIntentGenerator:
    generator_id = "fake-generator"

    def __init__(self, response):
        self.response = response
        self.calls = []

    async def generate_structured(self, *, system_instruction, input_payload, response_model):
        self.calls.append(
            {
                "system_instruction": system_instruction,
                "input_payload": input_payload,
                "response_model": response_model,
            }
        )
        return self.response


def _evidence(evidence_id: str, key: str = "visible_attribute", value: str = "visual_attribute_beta") -> EvidenceItem:
    return EvidenceItem(
        evidence_id=evidence_id,
        key=key,
        value=value,
        source="image_vlm",
        evidence_class="visual_observation",
        confidence=0.9,
        usable_for_copy=True,
    )


def _context(**overrides) -> CreativeRoutingContext:
    domain = DomainRoutingResult(
        raw_business_type="retail",
        canonical_domain=CanonicalBusinessDomain.RETAIL,
        support_status=DomainSupportStatus.SPECIALIZED,
        evidence_refs=["domain:e1"],
        confidence=0.9,
    )
    business = BusinessEnvironmentContext(
        broad_domain=CanonicalBusinessDomain.RETAIL,
        business_tags=["business_tag_epsilon"],
        evidence_refs=["business:e1"],
        confidence=0.8,
    )
    product = ProductUnderstanding(
        product_name="product_fact_alpha",
        normalized_product_type="product_fact_alpha",
        broad_category="other",
        category_path=["other", "product_fact_alpha"],
        product_name_evidence_ids=["product:e1"],
        confidence=0.86,
    )
    product_visual = ProductVisualContext(
        product_name="product_fact_alpha",
        category_path=["other", "product_fact_alpha"],
        product_tags=["product_fact_alpha"],
        visible_attributes=["visual_attribute_beta"],
        explicit_preparation_methods=["preparation_gamma"],
        permissible_visual_inferences=["permissible_zeta"],
        prohibited_visual_inferences=["prohibited_delta"],
        evidence_refs=["product_visual:e1"],
        confidence=0.84,
    )
    campaign = CampaignContext(
        campaign_intent="campaign_theta",
        evidence_refs=["campaign:e1"],
        confidence=0.7,
    )
    visual = [_evidence("visual:e1")]
    conflict = [
        InputConflict(
            conflict_id="conflict:e1",
            field="field_alpha",
            conflict_type="intent_mismatch",
            severity="manual_review",
            confidence=0.7,
            recommended_resolution="review",
        )
    ]
    kwargs = {
        "domain": domain,
        "business": business,
        "product": product,
        "product_visual": product_visual,
        "campaign": campaign,
        "ad_format": build_ad_format_spec("poster"),
        "visual_observations": visual,
        "reference_style_profile": {"style_token": "reference_style_eta"},
        "ambiguity_flags": ["ambiguous_alpha"],
        "input_conflicts": conflict,
        "resolver_version": "visual-strategy-resolver-v1",
    }
    kwargs.update(overrides)
    return build_creative_routing_context(**kwargs)


def _intent(required=None, prohibited=None, mood="novel_semantic_token_572") -> VisualSemanticIntent:
    return VisualSemanticIntent(
        subject_priority=0.8,
        environment_priority=0.7,
        text_priority=0.6,
        desired_moods=[mood] if mood else [],
        required_visual_facts=required or ["product_fact_alpha"],
        prohibited_visual_elements=prohibited or ["prohibited_delta"],
        copy_presence_mode="open_copy_mode_alpha",
        confidence=0.9,
    )


def _attributions(intent: VisualSemanticIntent) -> list[SemanticIntentAttribution]:
    attrs = [
        SemanticIntentAttribution(field_name="subject_priority", source_paths=["$.product.product_name"], is_derived=True),
        SemanticIntentAttribution(field_name="environment_priority", source_paths=["$.business.confidence"], is_derived=True),
        SemanticIntentAttribution(field_name="text_priority", source_paths=["$.ad_format.ad_format"], is_derived=True),
        SemanticIntentAttribution(field_name="copy_presence_mode", item_value=intent.copy_presence_mode, source_paths=["$.ad_format.information_density"], is_derived=True),
        SemanticIntentAttribution(field_name="confidence", source_paths=["$.product_visual.confidence"], is_derived=True),
    ]
    for value in intent.desired_moods:
        attrs.append(SemanticIntentAttribution(field_name="desired_moods", item_value=value, source_paths=["$.reference_style_profile.style_token"], is_derived=True))
    for value in intent.required_visual_facts:
        attrs.append(SemanticIntentAttribution(field_name="required_visual_facts", item_value=value, evidence_refs=["product_visual:e1"], source_paths=["$.product_visual.product_tags[0]"], is_derived=False))
    for value in intent.prohibited_visual_elements:
        attrs.append(SemanticIntentAttribution(field_name="prohibited_visual_elements", item_value=value, evidence_refs=["product_visual:e1"], source_paths=["$.product_visual.prohibited_visual_inferences[0]"], is_derived=False))
    return attrs


def _draft(intent: VisualSemanticIntent | None = None) -> VisualSemanticIntentDraft:
    resolved = intent or _intent()
    return VisualSemanticIntentDraft(intent=resolved, attributions=_attributions(resolved), ambiguity_flags=["ambiguous_alpha"])


def _run(coro):
    return asyncio.run(coro)


def test_generate_visual_semantic_intent_uses_projection_and_fake_generator():
    generator = FakeStructuredSemanticIntentGenerator(_draft())

    result = _run(generate_visual_semantic_intent(_context(), generator=generator))

    assert result.intent.required_visual_facts == ("product_fact_alpha",)
    assert result.generator_id == "fake-generator"
    call = generator.calls[0]
    assert call["response_model"] is VisualSemanticIntentDraft
    assert "metadata" not in call["input_payload"]["context"]["ad_format"]
    assert "business_type" not in call["input_payload"]["context"]["domain"]
    assert "product_fact_alpha" in call["input_payload"]["grounding_contract"]["required_fact_candidates"]
    assert "prohibited_delta" in call["input_payload"]["grounding_contract"]["prohibited_element_candidates"]
    assert "model_name" not in call["system_instruction"]
    assert "product_fact_alpha" not in call["system_instruction"]


def test_projection_and_grounding_snapshot_are_dynamic():
    context = _context()
    projection = build_visual_semantic_input_projection(context)
    snapshot = build_semantic_grounding_snapshot(context, projection)

    assert projection["product_visual"]["prohibited_visual_inferences"] == ["prohibited_delta"]
    assert "business_tag_epsilon" not in snapshot.required_fact_candidates
    assert "business_tag_epsilon" not in snapshot.prohibited_element_candidates
    assert "permissible_zeta" not in snapshot.required_fact_candidates
    assert "permissible_zeta" in snapshot.permissible_semantic_candidates
    assert "product_fact_alpha" in snapshot.required_fact_candidates
    assert "prohibited_delta" in snapshot.prohibited_element_candidates
    assert "domain:e1" in snapshot.available_evidence_refs
    assert "product_visual:e1" in snapshot.available_evidence_refs
    assert "$.product_visual.product_tags[0]" in snapshot.available_source_paths
    assert "$.product_visual" not in snapshot.available_source_paths


def test_ungrounded_required_or_prohibited_items_are_rejected():
    with pytest.raises(VisualSemanticIntentGroundingError):
        _run(generate_visual_semantic_intent(_context(), generator=FakeStructuredSemanticIntentGenerator(_draft(_intent(required=["unknown_required"])))))
    with pytest.raises(VisualSemanticIntentGroundingError):
        _run(generate_visual_semantic_intent(_context(), generator=FakeStructuredSemanticIntentGenerator(_draft(_intent(prohibited=["unknown_prohibited"])))))
    with pytest.raises(VisualSemanticIntentGroundingError):
        _run(generate_visual_semantic_intent(_context(), generator=FakeStructuredSemanticIntentGenerator(_draft(_intent(required=["permissible_zeta"])))))


def test_attribution_validation_rejects_invented_refs_paths_and_missing_items():
    intent = _intent()
    bad_ref = VisualSemanticIntentDraft(
        intent=intent,
        attributions=[*_attributions(intent), SemanticIntentAttribution(field_name="desired_moods", item_value="x", evidence_refs=["invented"], is_derived=True)],
    )
    with pytest.raises(VisualSemanticIntentValidationError, match="evidence_ref"):
        _run(generate_visual_semantic_intent(_context(), generator=FakeStructuredSemanticIntentGenerator(bad_ref)))

    bad_path = VisualSemanticIntentDraft(
        intent=intent,
        attributions=[*_attributions(intent), SemanticIntentAttribution(field_name="desired_moods", item_value="x", source_paths=["$.missing"], is_derived=True)],
    )
    with pytest.raises(VisualSemanticIntentValidationError, match="source_path"):
        _run(generate_visual_semantic_intent(_context(), generator=FakeStructuredSemanticIntentGenerator(bad_path)))

    missing = VisualSemanticIntentDraft(intent=intent, attributions=_attributions(intent)[:-1])
    with pytest.raises(VisualSemanticIntentValidationError, match="missing attribution"):
        _run(generate_visual_semantic_intent(_context(), generator=FakeStructuredSemanticIntentGenerator(missing)))


def test_strong_fact_attribution_must_match_leaf_source_value_and_not_be_derived():
    intent = _intent()
    unrelated = _attributions(intent)
    unrelated[-2] = SemanticIntentAttribution(
        field_name="required_visual_facts",
        item_value="product_fact_alpha",
        source_paths=["$.campaign.campaign_intent"],
        is_derived=False,
    )
    with pytest.raises(VisualSemanticIntentValidationError, match="source_path must match"):
        _run(generate_visual_semantic_intent(_context(), generator=FakeStructuredSemanticIntentGenerator(VisualSemanticIntentDraft(intent=intent, attributions=unrelated))))

    derived = _attributions(intent)
    derived[-2] = SemanticIntentAttribution(
        field_name="required_visual_facts",
        item_value="product_fact_alpha",
        source_paths=["$.product_visual.product_tags[0]"],
        is_derived=True,
    )
    with pytest.raises(VisualSemanticIntentValidationError, match="must not be derived"):
        _run(generate_visual_semantic_intent(_context(), generator=FakeStructuredSemanticIntentGenerator(VisualSemanticIntentDraft(intent=intent, attributions=derived))))

    container = _attributions(intent)
    container[-1] = SemanticIntentAttribution(
        field_name="prohibited_visual_elements",
        item_value="prohibited_delta",
        source_paths=["$.product_visual"],
        is_derived=False,
    )
    with pytest.raises(VisualSemanticIntentValidationError, match="source_path"):
        _run(generate_visual_semantic_intent(_context(), generator=FakeStructuredSemanticIntentGenerator(VisualSemanticIntentDraft(intent=intent, attributions=container))))


def test_attribution_schema_rejects_unknown_field_and_empty_grounding():
    with pytest.raises(ValueError):
        SemanticIntentAttribution(field_name="desired_moods", item_value="x", is_derived=True)

    intent = _intent()
    draft = VisualSemanticIntentDraft(
        intent=intent,
        attributions=[*_attributions(intent), SemanticIntentAttribution(field_name="unknown_field", source_paths=["$.product.product_name"], is_derived=True)],
    )
    with pytest.raises(VisualSemanticIntentValidationError, match="unknown attribution"):
        _run(generate_visual_semantic_intent(_context(), generator=FakeStructuredSemanticIntentGenerator(draft)))


def test_reserved_identifier_policy_is_injected_not_hardcoded():
    policy = VisualSemanticIntentValidationPolicy(reserved_internal_identifiers=frozenset({"internal_ref_alpha_9281"}))
    with pytest.raises(VisualSemanticIntentIdentifierLeakError):
        _run(generate_visual_semantic_intent(_context(), generator=FakeStructuredSemanticIntentGenerator(_draft(_intent(mood="internal_ref_alpha_9281"))), validation_policy=policy))

    result = _run(generate_visual_semantic_intent(_context(), generator=FakeStructuredSemanticIntentGenerator(_draft(_intent(mood="novel_semantic_token_572"))), validation_policy=policy))
    assert result.intent.desired_moods == ("novel_semantic_token_572",)


def test_reserved_identifier_is_blocked_in_ambiguity_and_attribution_item_value():
    policy = VisualSemanticIntentValidationPolicy(reserved_internal_identifiers=frozenset({"internal_ref_alpha_9281"}))
    with pytest.raises(VisualSemanticIntentIdentifierLeakError):
        _run(generate_visual_semantic_intent(_context(), generator=FakeStructuredSemanticIntentGenerator(VisualSemanticIntentDraft(intent=_intent(), attributions=_attributions(_intent()), ambiguity_flags=["internal_ref_alpha_9281"])), validation_policy=policy))

    attrs = _attributions(_intent())
    attrs[0] = SemanticIntentAttribution(field_name="subject_priority", item_value="internal_ref_alpha_9281", source_paths=["$.product.product_name"], is_derived=True)
    with pytest.raises(VisualSemanticIntentIdentifierLeakError):
        _run(generate_visual_semantic_intent(_context(), generator=FakeStructuredSemanticIntentGenerator(VisualSemanticIntentDraft(intent=_intent(), attributions=attrs)), validation_policy=policy))


def test_upstream_ambiguity_flags_are_preserved_and_merged():
    draft = VisualSemanticIntentDraft(intent=_intent(), attributions=_attributions(_intent()), ambiguity_flags=["ambiguous_alpha", "new_flag"])
    result = _run(generate_visual_semantic_intent(_context(), generator=FakeStructuredSemanticIntentGenerator(draft)))

    assert result.ambiguity_flags == ("ambiguous_alpha", "new_flag")


def test_product_required_prohibited_facts_are_not_changed_by_business_campaign_format_or_reference():
    base = _context()
    changed_business = _context(business=BusinessEnvironmentContext(broad_domain=CanonicalBusinessDomain.RETAIL, environment_tags=["venue_style_gamma"], evidence_refs=["business:e2"], confidence=0.8))
    changed_campaign = _context(campaign=CampaignContext(campaign_intent="campaign_variant", evidence_refs=["campaign:e2"], confidence=0.7))
    changed_format = _context(ad_format=build_ad_format_spec("banner"))
    changed_reference = _context(reference_style_profile={"style_token": "reference_variant"})
    draft = _draft(_intent(required=["product_fact_alpha"], prohibited=["prohibited_delta"]))
    for context in (base, changed_business, changed_campaign, changed_format, changed_reference):
        result = _run(generate_visual_semantic_intent(context, generator=FakeStructuredSemanticIntentGenerator(draft)))
        assert result.intent.required_visual_facts == ("product_fact_alpha",)
        assert result.intent.prohibited_visual_elements == ("prohibited_delta",)


def test_system_instruction_has_no_fixture_examples_or_semantic_whitelist():
    forbidden = [
        "fried_potato",
        "grilled_meat",
        "korean_bbq",
        "charcoal",
        "open_flame",
        "appetizing",
        "ceramic_plate",
        "warm_side_light",
    ]

    assert all(item not in SYSTEM_INSTRUCTION for item in forbidden)
