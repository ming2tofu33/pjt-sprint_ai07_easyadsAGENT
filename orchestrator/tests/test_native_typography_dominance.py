from orchestrator.app.llm.native_campaign_message_service import plan_typography_dominance
from orchestrator.app.schemas.native_creative import CampaignMessagePlan


def test_new_product_intro_uses_medium_headline_and_small_support():
    campaign = CampaignMessagePlan(campaign_role="new_product_introduction", primary_communication_goal="new_product_launch", funnel_stage="awareness", image_explanatory_power=0.7, verified_information_density="low", visible_copy_mode="headline_plus_support", headline_function="launch_announcement", support_function="launch_context", rationale=[], confidence=0.8)

    plan = plan_typography_dominance(campaign_plan=campaign, placement="instagram_feed_static")

    assert plan.headline_prominence == "balanced"
    assert plan.headline_scale_intent == "medium"
    assert plan.support_scale_intent == "small"
    assert plan.product_visual_priority >= 0.7
