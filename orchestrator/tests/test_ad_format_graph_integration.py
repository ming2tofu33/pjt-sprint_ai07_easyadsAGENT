from orchestrator.app.graph.builder import build_marketing_graph
from orchestrator.app.llm.nodes.copy_spec_parser import copy_spec_parser_node
from orchestrator.app.llm.nodes.image_prompt_planner import build_ad_format_composition_hint
from orchestrator.app.llm.nodes.text_style_binder import text_style_binder_node
from orchestrator.app.llm.nodes.text_layout_planner import text_layout_planner_node


def _config(thread_id: str):
    return {"configurable": {"thread_id": thread_id}}


def _request(job_id: str, text: str, ad_format: str = "instagram_feed", goal: str = "brand_awareness"):
    return {
        "user_input": text,
        "job_id": job_id,
        "thread_id": job_id,
        "copy_generation_mode": "auto_pilot",
        "context": {
            "business_type": "cafe",
            "item_or_service": "macaron",
            "promotion_goal": goal,
            "extra": {"ad_format": ad_format},
        },
    }


def test_graph_populates_ad_format_contract_fields():
    graph = build_marketing_graph()
    result = graph.invoke(_request("ad-format-graph-feed", "editorial macaron visual", "instagram_feed"), config=_config("ad-format-graph-feed"))

    assert result["ad_format_contract"]["placement"] == "instagram_feed_static"
    assert result["creative_lane_decision"]["lane"] == "visual_first"
    assert result["copy_presence_plan"]["max_text_area_ratio"] <= 0.15
    assert result["information_panel_plan"]["enabled"] is False


def test_copy_spec_parser_removes_forbidden_cta():
    state = {
        "copy_presence_plan": {"allowed_roles": ["headline"], "forbidden_roles": ["cta", "embedded_action_cta"]},
        "marketing_copy": {"headline": "Macaron", "subcopy": "Soft color", "cta": "Buy now", "metadata": {}},
        "context": {"business_type": "cafe", "promotion_goal": "brand_awareness", "extra": {}},
        "copy_visual_intent": {"hierarchy": "minimal_premium", "headline_emphasis": "large_bold", "body_density": "low", "cta_visibility": "required", "cta_style": "pill_button", "preferred_alignment": "center", "typography_mood": "clean_sans", "plate_policy": "none", "product_text_relationship": "centered_minimal"},
    }

    result = copy_spec_parser_node(state)

    assert [item["role"] for item in result["copy_spec"]["items"]] == ["headline"]


def test_layout_planner_respects_information_panel_and_text_budget():
    state = {
        "copy_spec": {"items": [{"role": "headline", "text": "Sale", "priority": 1}, {"role": "price", "text": "20%", "priority": 2}], "copy_mode": "standard"},
        "context": {"business_type": "retail", "item_or_service": "seasonal collection", "promotion_goal": "discount_event", "extra": {}},
        "ad_format_spec": {"ad_format": "poster", "width": 1000, "height": 1000},
        "copy_presence_plan": {"max_text_area_ratio": 0.65, "allowed_roles": ["headline", "price"], "forbidden_roles": []},
        "information_panel_plan": {"enabled": True, "panel_type": "split_screen_diagonal_panel", "coverage_ratio": 0.55, "safe_margin_ratio": 0.05},
    }
    state.update(text_style_binder_node(state))

    result = text_layout_planner_node(state)
    layout = result["text_layout_spec"]

    assert layout["template"] == "right_text_left_product"
    assert sum(slot["bbox"]["w"] * slot["bbox"]["h"] for slot in layout["slots"]) <= 0.65


def test_image_prompt_hint_mentions_panel_and_cta_policy():
    hint = build_ad_format_composition_hint(
        {"embedded_cta_policy": "platform_only", "platform_safe_zones": {"bottom_ratio": 0.12}},
        {"lane": "information_design"},
        {"mode": "product_benefit_summary", "max_text_area_ratio": 0.35},
        {"enabled": True, "panel_type": "left_information_column", "geometry": "rounded_rectangle", "coverage_ratio": 0.38, "product_zone": "right"},
    )

    assert "left_information_column" in hint
    assert "Do not render embedded button-style CTA" in hint
