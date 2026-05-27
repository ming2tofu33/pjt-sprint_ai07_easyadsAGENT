from orchestrator.app.graph.state import create_initial_marketing_state
from orchestrator.app.llm.nodes.format_planner import format_planner_node
from orchestrator.app.schemas.llm_marketing import InitialMarketingRequest, MarketingContext


def _state(ad_format="instagram_feed", current_ad_format=None):
    state = create_initial_marketing_state(
        InitialMarketingRequest(
            user_input="ready",
            context=MarketingContext(
                business_type="restaurant",
                item_or_service="삼겹살",
                promotion_goal="reservation_cta",
                extra={"ad_format": ad_format},
            ),
        )
    )
    if current_ad_format:
        state["current_brief"]["requested_ad_format"] = current_ad_format
    return state


def test_format_planner_uses_instagram_feed_preset():
    update = format_planner_node(_state("instagram_feed"))

    assert update["ad_format_spec"]["ad_format"] == "instagram_feed"
    assert update["ad_format_spec"]["width"] == 1080
    assert update["ad_format_spec"]["height"] == 1080
    assert update["layout_spec"]["layout_type"] == "single_hero"


def test_format_planner_uses_context_extra_ad_format():
    update = format_planner_node(_state("flyer"))

    assert update["ad_format_spec"]["ad_format"] == "flyer"
    assert update["ad_format_spec"]["aspect_ratio"] == "A4_vertical"
    assert update["layout_spec"]["layout_type"] == "flyer_information"


def test_format_planner_prefers_current_brief_requested_ad_format():
    update = format_planner_node(_state("instagram_feed", current_ad_format="banner"))

    assert update["ad_format_spec"]["ad_format"] == "banner"
    assert update["layout_spec"]["layout_type"] == "split_text_image"


def test_product_detail_uses_smartstore_platform():
    update = format_planner_node(_state("product_detail"))

    assert update["ad_format_spec"]["platform"] == "naver_smartstore"
    assert update["layout_spec"]["product_zone"] is not None
