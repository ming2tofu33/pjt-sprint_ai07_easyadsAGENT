from orchestrator.app.llm.ad_format_policy import build_ad_format_contract, build_copy_presence_plan, decide_creative_lane


def _plan(user_input: str, ad_format: str = "instagram_feed", goal: str = "brand_awareness"):
    state = {
        "user_input": user_input,
        "current_brief": {"requested_ad_format": ad_format},
        "context": {"business_type": "cafe", "item_or_service": "macaron", "promotion_goal": goal, "extra": {"ad_format": ad_format}},
    }
    contract = build_ad_format_contract(state)
    lane = decide_creative_lane(state, contract)
    return build_copy_presence_plan(contract, lane, state), lane


def test_visual_first_text_budget_capped_at_15_percent():
    plan, lane = _plan("editorial macaron visual")

    assert lane.lane == "visual_first"
    assert plan.max_text_area_ratio <= 0.15
    assert "cta" in plan.forbidden_roles


def test_information_design_sale_poster_budget():
    plan, lane = _plan("seasonal sale 20% 5.20-5.27 price 29000원", "poster", "discount_event")

    assert lane.lane == "information_design"
    assert plan.mode == "full_information_poster"
    assert plan.min_text_area_ratio == 0.40
    assert plan.max_text_area_ratio == 0.65


def test_story_platform_cta_forbids_embedded_action_cta():
    plan, _lane = _plan("serum benefits glow moisture calming 20% 5.20-5.27", "instagram_story", "conversion")

    assert "embedded_action_cta" in plan.forbidden_roles
    assert "cta" in plan.forbidden_roles
