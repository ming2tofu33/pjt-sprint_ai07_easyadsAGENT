from orchestrator.app.graph.state import create_initial_marketing_state
from orchestrator.app.llm.nodes.copy_spec_parser import copy_spec_parser_node
from orchestrator.app.llm.nodes.format_planner import format_planner_node
from orchestrator.app.llm.nodes.image_prompt_planner import image_prompt_planner_node
from orchestrator.app.llm.nodes.no_copy import no_copy_bypass_node
from orchestrator.app.llm.nodes.text_layout_planner import text_layout_planner_node
from orchestrator.app.llm.nodes.text_style_binder import text_style_binder_node
from orchestrator.app.schemas.llm_marketing import InitialMarketingRequest, MarketingContext


def test_no_copy_branch_builds_no_text_tlfp_specs():
    state = create_initial_marketing_state(
        InitialMarketingRequest(
            user_input="ready",
            copy_generation_mode="no_copy",
            context=MarketingContext(business_type="restaurant", item_or_service="삼겹살", promotion_goal="reservation_cta", extra={"ad_format": "instagram_feed"}),
        )
    )
    state.update(format_planner_node(state))
    state.update(no_copy_bypass_node(state))
    state.update(copy_spec_parser_node(state))
    state.update(text_style_binder_node(state))
    state.update(text_layout_planner_node(state))
    state.update(image_prompt_planner_node(state))

    assert state["copy_required"] is False
    assert state["text_overlay_pending"] is False
    assert state["copy_spec"]["copy_mode"] == "no_copy"
    assert state["copy_spec"]["items"] == []
    assert state["text_layout_spec"]["template"] == "no_text"
    assert state["text_layout_spec"]["reserved_text_areas"] == []
    assert state["image_prompt_spec"]["must_not_include_text"] is True
    for phrase in ["text", "letters", "hangul", "watermark", "logo"]:
        assert phrase in state["image_prompt_spec"]["negative_prompt_en"]
