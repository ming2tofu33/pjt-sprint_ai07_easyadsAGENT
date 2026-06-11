from orchestrator.app.llm.ad_format_policy import build_ad_format_contract, build_information_panel_plan, decide_creative_lane


def _panel(user_input: str, ad_format: str = "instagram_feed", goal: str = "brand_awareness"):
    benefits = ["glow", "moisture", "calming"] if "benefit" in user_input or "glow" in user_input else []
    state = {
        "user_input": user_input,
        "current_brief": {"requested_ad_format": ad_format},
        "context": {
            "business_type": "beauty_skincare",
            "item_or_service": "serum",
            "promotion_goal": goal,
            "extra": {"ad_format": ad_format, "benefits": benefits},
        },
    }
    contract = build_ad_format_contract(state)
    lane = decide_creative_lane(state, contract)
    return build_information_panel_plan(contract, lane), lane


def test_visual_first_has_no_information_panel():
    panel, lane = _panel("editorial macaron visual", "instagram_feed")

    assert lane.lane == "visual_first"
    assert panel.enabled is False
    assert panel.panel_type == "none"


def test_serum_story_uses_information_column_panel():
    panel, lane = _panel("serum benefits glow moisture calming 20% 5.20-5.27", "instagram_story", "conversion")

    assert lane.lane == "information_design"
    assert panel.enabled is True
    assert panel.panel_type == "left_information_column"
    assert "benefit_list_zone" in panel.hierarchy_zones


def test_sale_poster_uses_sale_panel_geometry():
    panel, lane = _panel("sale 20% 5.20-5.27 price 29000원", "poster", "discount_event")

    assert lane.archetype == "promotion_sale_poster"
    assert panel.enabled is True
    assert panel.coverage_ratio == 0.55
    assert panel.geometry == "diagonal"
