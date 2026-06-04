from orchestrator.app.graph.state import create_initial_marketing_state
from orchestrator.app.llm.nodes.copy_spec_parser import copy_spec_parser_node
from orchestrator.app.llm.nodes.format_planner import format_planner_node
from orchestrator.app.llm.nodes.text_layout_planner import text_layout_planner_node
from orchestrator.app.llm.nodes.text_style_binder import text_style_binder_node
from orchestrator.app.schemas.llm_marketing import InitialMarketingRequest, MarketingContext


def _planned_state(ad_format="instagram_feed"):
    state = create_initial_marketing_state(
        InitialMarketingRequest(
            user_input="ready",
            context=MarketingContext(business_type="restaurant", item_or_service="삼겹살", promotion_goal="reservation_cta", extra={"ad_format": ad_format}),
        )
    )
    state.update(format_planner_node(state))
    state["marketing_copy"] = {"headline": "오늘 회식은 삼겹살로 결정", "subcopy": "편안한 자리", "cta": "예약 문의하기", "metadata": {}}
    state.update(copy_spec_parser_node(state))
    state.update(text_style_binder_node(state))
    return state


def test_text_layout_planner_templates_by_ad_format():
    assert text_layout_planner_node(_planned_state("instagram_feed"))["text_layout_spec"]["template"] == "top_headline_center_product_bottom_cta"
    assert text_layout_planner_node(_planned_state("banner"))["text_layout_spec"]["template"] == "left_text_right_product"
    assert text_layout_planner_node(_planned_state("flyer"))["text_layout_spec"]["template"] == "multi_zone_flyer"


def test_text_layout_planner_bbox_ranges_and_reserved_sync():
    spec = text_layout_planner_node(_planned_state("instagram_feed"))["text_layout_spec"]

    assert spec["reserved_text_areas"]
    for slot in spec["slots"]:
        bbox = slot["bbox"]
        assert 0 <= bbox["x"] <= 1
        assert 0 <= bbox["y"] <= 1
        assert bbox["x"] + bbox["w"] <= 1
        assert bbox["y"] + bbox["h"] <= 1
    product = spec["product_zone"]
    assert product["y"] >= 0.30


def test_text_layout_planner_no_text_allows_empty_slots():
    state = _planned_state("instagram_feed")
    state["copy_spec"]["copy_mode"] = "no_copy"
    state["copy_spec"]["items"] = []
    spec = text_layout_planner_node(state)["text_layout_spec"]

    assert spec["template"] == "no_text"
    assert spec["slots"] == []
    assert spec["reserved_text_areas"] == []
