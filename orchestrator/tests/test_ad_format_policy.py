from orchestrator.app.llm.ad_format_policy import build_ad_format_contract


def _state(ad_format: str, user_input: str = "premium macaron product photo"):
    return {
        "user_input": user_input,
        "current_brief": {"requested_ad_format": ad_format},
        "context": {"business_type": "cafe", "item_or_service": "macaron", "promotion_goal": "brand_awareness", "extra": {"ad_format": ad_format}},
    }


def test_instagram_story_uses_platform_cta_policy():
    contract = build_ad_format_contract(_state("instagram_story", "serum benefits 20% 5.20-5.27"))

    assert contract.interaction_mode == "platform_interactive"
    assert contract.platform_cta_available is True
    assert contract.embedded_cta_policy == "platform_only"
    assert contract.platform_safe_zones.bottom_ratio == 0.12


def test_instagram_feed_embedded_cta_forbidden_by_default():
    contract = build_ad_format_contract(_state("instagram_feed"))

    assert contract.placement == "instagram_feed_static"
    assert contract.interaction_mode == "non_interactive_image"
    assert contract.embedded_cta_policy == "forbidden"
    assert contract.caption_channel_available is True


def test_landing_page_hero_forbids_embedded_cta():
    contract = build_ad_format_contract(_state("landing_page"))

    assert contract.interaction_mode == "html_or_landing_page"
    assert contract.embedded_cta_policy == "forbidden"


def test_print_poster_without_destination_does_not_require_fake_button():
    contract = build_ad_format_contract(_state("poster", "seasonal sale 20% 5.20-5.27"))

    assert contract.interaction_mode == "print_or_offline"
    assert contract.embedded_cta_policy == "optional"
    assert contract.creative_lane == "information_design"
