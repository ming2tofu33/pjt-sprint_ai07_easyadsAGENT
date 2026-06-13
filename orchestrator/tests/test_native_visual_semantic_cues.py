from orchestrator.app.llm.native_campaign_message_service import build_visual_semantic_cue_plan
from orchestrator.app.schemas.input_evidence import EvidenceItem, InputEvidenceBundle
from orchestrator.app.schemas.native_creative import CampaignMessagePlan
from orchestrator.app.schemas.product_understanding import ProductUnderstanding


def test_visual_semantic_cues_are_not_visible_copy():
    fact = EvidenceItem(key="product_name", value="Product A", source="user_text", evidence_class="verified_fact", confidence=1.0, usable_for_copy=True)
    evidence = InputEvidenceBundle(input_mode="text_only", user_text="Make a refined ad for Product A", user_request_utterance="Make a refined ad for Product A", desired_positioning=["premium", "refined"], explicit_product_mentions=["Product A"], explicit_user_facts=[fact], overall_confidence=0.9)
    product = ProductUnderstanding(product_name="Product A", normalized_product_type="product", broad_category="other", category_path=["other"], verified_facts=[fact], product_name_evidence_ids=[fact.evidence_id], confidence=0.9)
    campaign = CampaignMessagePlan(campaign_role="menu_identity", primary_communication_goal="product_promotion", funnel_stage="awareness", image_explanatory_power=0.8, verified_information_density="minimal", visible_copy_mode="product_name_only", headline_function="product_identity", support_function="none", rationale=[], confidence=0.8)

    plan = build_visual_semantic_cue_plan(campaign_plan=campaign, input_evidence=evidence, product_understanding=product)

    assert plan.non_display_cues
    assert "Product A" not in plan.must_not_render_as_text
    assert set(plan.non_display_cues).issubset(set(plan.must_not_render_as_text))
