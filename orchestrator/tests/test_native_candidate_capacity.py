from orchestrator.app.llm.native_copy_candidate_service import coerce_native_copy_strategy_bundle
from orchestrator.app.schemas.input_evidence import EvidenceItem, InputEvidenceBundle
from orchestrator.app.schemas.native_creative import CampaignMessagePlan
from orchestrator.app.schemas.product_understanding import ProductUnderstanding


def _base():
    fact = EvidenceItem(key="product_name", value="Product A", source="user_text", evidence_class="verified_fact", confidence=1.0, usable_for_copy=True)
    evidence = InputEvidenceBundle(input_mode="text_only", user_text="Promote Product A", user_request_utterance="Promote Product A", explicit_product_mentions=["Product A"], explicit_user_facts=[fact], overall_confidence=0.9)
    product = ProductUnderstanding(product_name="Product A", normalized_product_type="product", broad_category="other", category_path=["other"], verified_facts=[fact], product_name_evidence_ids=[fact.evidence_id], confidence=0.9)
    return fact, evidence, product


def test_product_name_only_basis_uses_single_minimal_capacity():
    fact, evidence, product = _base()
    bundle = coerce_native_copy_strategy_bundle({"candidates": [{"candidate_id": "c1", "strategy": "minimal_identity", "headline": "Product A", "headline_basis_ids": [fact.evidence_id]}]}, input_evidence=evidence, product_understanding=product)

    assert bundle.candidate_capacity == "single_minimal"
    assert bundle.effective_candidate_count == 1


def test_launch_campaign_allows_limited_candidates():
    fact, evidence, product = _base()
    campaign = CampaignMessagePlan(campaign_role="new_product_introduction", primary_communication_goal="new_product_launch", funnel_stage="awareness", image_explanatory_power=0.7, verified_information_density="minimal", visible_copy_mode="headline_plus_support", headline_function="launch_announcement", support_function="launch_context", rationale=[], confidence=0.8)
    bundle = coerce_native_copy_strategy_bundle({"campaign_message_plan": campaign.model_dump(), "candidates": [{"candidate_id": f"c{i}", "strategy": "campaign_context", "headline": f"Product A {i}", "supporting_copy": "New menu introduction", "headline_basis_ids": [fact.evidence_id], "support_basis_type": "campaign_context"} for i in range(4)]}, input_evidence=evidence, product_understanding=product)

    assert bundle.candidate_capacity == "limited"
    assert 1 <= bundle.effective_candidate_count <= 3
