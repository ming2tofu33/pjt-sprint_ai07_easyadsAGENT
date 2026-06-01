from orchestrator.app.graph.state import create_initial_marketing_state
from orchestrator.app.llm.nodes.copy_spec_parser import copy_spec_parser_node
from orchestrator.app.llm.nodes.format_planner import format_planner_node
import json

from orchestrator.app.llm.nodes.image_prompt_planner import bbox_to_natural_language, build_image_prompt_planner_prompt, image_prompt_planner_node, infer_copy_space_from_reserved_areas
from orchestrator.app.llm.nodes.text_layout_planner import text_layout_planner_node
from orchestrator.app.llm.nodes.text_style_binder import text_style_binder_node
from orchestrator.app.schemas.llm_marketing import InitialMarketingRequest, MarketingContext
from orchestrator.app.schemas.text_layout import NormalizedBBox


def _state():
    state = create_initial_marketing_state(
        InitialMarketingRequest(
            user_input="ready",
            context=MarketingContext(business_type="restaurant", item_or_service="삼겹살", promotion_goal="reservation_cta", extra={"ad_format": "instagram_feed"}),
        )
    )
    state.update(format_planner_node(state))
    state["marketing_copy"] = {"headline": "오늘 회식은 삼겹살로 결정", "subcopy": "편안한 자리", "cta": "예약 문의하기", "metadata": {}}
    state.update(copy_spec_parser_node(state))
    state.update(text_style_binder_node(state))
    state.update(text_layout_planner_node(state))
    return state


def test_bbox_to_natural_language_mentions_position_and_size():
    phrase = bbox_to_natural_language(NormalizedBBox(x=0.05, y=0.06, w=0.90, h=0.18))

    assert "upper center" in phrase
    assert "clean empty area" in phrase


def test_infer_copy_space_from_reserved_area():
    assert infer_copy_space_from_reserved_areas([NormalizedBBox(x=0.05, y=0.06, w=0.90, h=0.18)]) == "top"
    assert infer_copy_space_from_reserved_areas([NormalizedBBox(x=0.30, y=0.86, w=0.40, h=0.08)]) == "bottom"
    assert infer_copy_space_from_reserved_areas([]) == "none"


def test_image_prompt_planner_uses_reserved_text_areas_and_no_text_negative():
    update = image_prompt_planner_node(_state())
    spec = update["image_prompt_spec"]

    assert spec["reserved_text_areas"]
    assert "Reserve" in spec["positive_prompt_en"]
    assert spec["must_not_include_text"] is True
    for phrase in ["text", "letters", "numbers", "hangul", "watermark", "logo"]:
        assert phrase in spec["negative_prompt_en"]
    assert spec["target_width"] == 1080
    assert spec["target_height"] == 1080
    metadata = update["llm_call_results"][0]["metadata"]
    assert metadata["trace"]["node_name"] == "image_prompt_planner"
    assert metadata["available_state"]["text_layout_spec"]
    assert metadata["available_state"]["reserved_text_areas"] == spec["reserved_text_areas"]
    assert metadata["constraints"]["render_text_in_image"] is False
    assert metadata["constraints"]["must_not_include_text"] is True


def test_image_prompt_planner_includes_frontend_visual_choices():
    state = _state()
    state["current_brief"]["selected_channel_id"] = "poster"
    state["current_brief"]["selected_tone"] = "고급스러운"
    state["current_brief"]["custom_direction"] = "상품을 중앙에 더 크게 보여줘"
    state["context"]["brand_tone"] = "고급스러운"
    state["context"]["extra"]["selected_channel_id"] = "poster"
    state["context"]["extra"]["custom_direction"] = "상품을 중앙에 더 크게 보여줘"

    update = image_prompt_planner_node(state)
    spec = update["image_prompt_spec"]

    assert "상품을 중앙에 더 크게 보여줘" in spec["scene_description"]
    assert "상품을 중앙에 더 크게 보여줘" in spec["positive_prompt_en"]
    assert "고급스러운" in spec["positive_prompt_en"]
    assert spec["metadata"]["selected_channel_id"] == "poster"
    assert spec["metadata"]["selected_tone"] == "고급스러운"
    assert spec["metadata"]["custom_direction"] == "상품을 중앙에 더 크게 보여줘"


def test_image_prompt_planner_prompt_uses_json_metadata_contract():
    state = _state()
    state["selected_reference_template"] = {"template_id": "ref-1", "title": "Reference Feed"}
    state["product_preserve_spec"] = {"product_bbox": {"x": 0.3, "y": 0.3, "w": 0.4, "h": 0.4}}

    prompt = build_image_prompt_planner_prompt(state)
    metadata = _metadata_contract_from_prompt(prompt)

    assert metadata["trace"]["node_name"] == "image_prompt_planner"
    assert metadata["available_state"]["selected_reference_template"]["template_id"] == "ref-1"
    assert metadata["available_state"]["product_preserve_spec"]["product_bbox"]["w"] == 0.4
    assert metadata["constraints"]["negative_prompt_required_terms"] == ["text", "letters", "numbers", "Hangul", "logo", "watermark"]


def _metadata_contract_from_prompt(prompt: str) -> dict:
    marker = "metadata_contract="
    start = prompt.index(marker) + len(marker)
    metadata, _ = json.JSONDecoder().raw_decode(prompt[start:].strip())
    return metadata
