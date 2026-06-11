from orchestrator.app.llm.ad_format_policy import build_ad_format_contract, decide_creative_lane


def _state(user_input: str, ad_format: str = "instagram_feed", promotion_goal: str = "brand_awareness"):
    return {
        "user_input": user_input,
        "current_brief": {"requested_ad_format": ad_format},
        "context": {
            "business_type": "beauty_skincare",
            "item_or_service": "serum",
            "promotion_goal": promotion_goal,
            "extra": {"ad_format": ad_format, "benefits": ["glow", "moisture", "calming"]},
        },
    }


def test_visual_first_macaron_feed_selects_visual_lane():
    state = {
        "user_input": "editorial macaron product photo",
        "current_brief": {"requested_ad_format": "instagram_feed"},
        "context": {"business_type": "cafe", "item_or_service": "macaron", "promotion_goal": "brand_awareness", "extra": {"ad_format": "instagram_feed"}},
    }
    decision = decide_creative_lane(state, build_ad_format_contract(state))

    assert decision.lane == "visual_first"
    assert decision.archetype == "visual_editorial"


def test_benefit_discount_period_selects_information_design():
    state = _state("serum benefits 20% discount 5.20-5.27", "instagram_story", "conversion")
    decision = decide_creative_lane(state, build_ad_format_contract(state))

    assert decision.lane == "information_design"
    assert decision.archetype == "product_benefit_story"
    assert "multiple_verified_benefits" in decision.reason_codes


def test_sale_poster_selects_sale_archetype():
    state = _state("seasonal sale 20% discount 5.20-5.27 price 29000원", "poster", "discount_event")
    decision = decide_creative_lane(state, build_ad_format_contract(state))

    assert decision.lane == "information_design"
    assert decision.archetype == "promotion_sale_poster"
