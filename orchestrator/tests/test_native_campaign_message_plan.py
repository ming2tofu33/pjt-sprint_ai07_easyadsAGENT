from orchestrator.app.llm.native_campaign_message_service import plan_native_campaign_message
from orchestrator.app.schemas.input_evidence import EvidenceItem, InputEvidenceBundle
from orchestrator.app.schemas.product_understanding import ProductUnderstanding


def _models(user_text: str, goal: str):
    fact = EvidenceItem(key="product_name", value="Product A", source="user_text", evidence_class="verified_fact", confidence=1.0, usable_for_copy=True)
    campaign = EvidenceItem(key="campaign_status", value="new_menu", source="user_text", evidence_class="verified_fact", confidence=1.0, usable_for_copy=True)
    facts = [fact, campaign] if goal == "new_product_launch" else [fact]
    evidence = InputEvidenceBundle(input_mode="text_only", user_text=user_text, user_request_utterance=user_text, campaign_intent=goal, campaign_status="new_menu" if goal == "new_product_launch" else None, explicit_product_mentions=["Product A"], explicit_user_facts=facts, overall_confidence=0.9)
    product = ProductUnderstanding(product_name="Product A", normalized_product_type="product", broad_category="other", category_path=["other"], verified_facts=facts, product_name_evidence_ids=[fact.evidence_id], campaign_status="new_menu" if goal == "new_product_launch" else None, confidence=0.9)
    return evidence, product


def test_same_product_uses_different_copy_mode_by_campaign_goal():
    menu_evidence, menu_product = _models("Make a menu identity image for Product A", "product_promotion")
    launch_evidence, launch_product = _models("Introduce Product A as a new menu", "new_product_launch")

    menu = plan_native_campaign_message(input_evidence=menu_evidence, product_understanding=menu_product, placement="poster", promotion_goal="product_promotion", source_visual_analysis=None, state={})
    launch = plan_native_campaign_message(input_evidence=launch_evidence, product_understanding=launch_product, placement="instagram_feed_static", promotion_goal="new_product_launch", source_visual_analysis=None, state={})

    assert menu.campaign_role == "menu_identity"
    assert menu.visible_copy_mode == "product_name_only"
    assert launch.campaign_role == "new_product_introduction"
    assert launch.visible_copy_mode == "headline_only"
    assert launch.headline_function == "product_identity"
    assert launch.support_function == "none"
    assert launch.launch_visibility_policy == "implicit"
    assert launch.campaign_context_is_display_copy is False
