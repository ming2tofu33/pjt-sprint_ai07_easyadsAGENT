from orchestrator.app.llm.ad_format_policy import build_ad_format_contract, build_copy_presence_plan, decide_creative_lane, role_allowed


def _state(ad_format: str, text: str = "ready"):
    return {
        "user_input": text,
        "current_brief": {"requested_ad_format": ad_format},
        "context": {"business_type": "cafe", "item_or_service": "latte", "promotion_goal": "brand_awareness", "extra": {"ad_format": ad_format}},
    }


def test_instagram_story_platform_cta_not_renderable_role():
    state = _state("instagram_story", "serum benefits glow moisture calming")
    contract = build_ad_format_contract(state)
    plan = build_copy_presence_plan(contract, decide_creative_lane(state, contract), state)

    assert contract.embedded_cta_policy == "platform_only"
    assert role_allowed("cta", plan) is False


def test_instagram_feed_button_cta_forbidden():
    state = _state("instagram_feed")
    contract = build_ad_format_contract(state)
    plan = build_copy_presence_plan(contract, decide_creative_lane(state, contract), state)

    assert contract.embedded_cta_policy == "forbidden"
    assert role_allowed("embedded_action_cta", plan) is False


def test_qr_style_action_can_be_modeled_as_verified_information_not_button():
    state = _state("poster", "poster with QR destination address")
    contract = build_ad_format_contract(state)

    assert contract.interaction_mode == "print_or_offline"
    assert "action_destination" in contract.required_information_fields
