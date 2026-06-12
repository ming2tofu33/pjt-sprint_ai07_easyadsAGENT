import json

from orchestrator.app.graph.state import create_initial_marketing_state
from orchestrator.app.llm.nodes.copy_candidates import copy_candidate_generation_node, state_update_selected_copy_node
from orchestrator.app.llm.nodes.copy_spec_parser import copy_spec_parser_node
from orchestrator.app.schemas.llm_marketing import InitialMarketingRequest, MarketingContext


def _state():
    return create_initial_marketing_state(
        InitialMarketingRequest(
            user_input="ready",
            copy_generation_mode="suggest_candidates",
            context=MarketingContext(business_type="restaurant", item_or_service="삼겹살", promotion_goal="reservation_cta", extra={"ad_format": "instagram_feed"}),
        )
    )


def _state_for_context(business_type: str, item_or_service: str, promotion_goal: str):
    return create_initial_marketing_state(
        InitialMarketingRequest(
            user_input="ready",
            copy_generation_mode="suggest_candidates",
            context=MarketingContext(
                business_type=business_type,
                item_or_service=item_or_service,
                promotion_goal=promotion_goal,
                extra={"ad_format": "instagram_feed"},
            ),
        )
    )


def test_copy_candidate_generation_is_stable_and_safe():
    update = copy_candidate_generation_node(_state())
    candidates = update["copy_candidates"]
    rendered = " ".join(str(value) for candidate in candidates for value in candidate.values())

    assert [candidate["id"] for candidate in candidates] == ["copy_1", "copy_2"]
    assert "010-" not in rendered
    assert "주소" not in rendered
    assert "%" not in rendered
    json.dumps({"candidates": candidates}, ensure_ascii=False)


def test_copy_candidate_generation_does_not_leak_option_value_codes():
    state = _state()
    state["context"]["item_or_service"] = "reservation_service"

    update = copy_candidate_generation_node(state)
    rendered = " ".join(str(value) for candidate in update["copy_candidates"] for value in candidate.values())

    assert "reservation_service" not in rendered
    assert "예약 서비스" in rendered
    assert "한 판" not in rendered
    assert "회식은 역시 예약 서비스" not in rendered


def test_copy_candidate_generation_uses_cafe_appropriate_fallback_copy():
    update = copy_candidate_generation_node(_state_for_context("cafe", "딸기라떼", "discount_event"))
    rendered = " ".join(str(value) for candidate in update["copy_candidates"] for value in candidate.values())

    assert "딸기라떼" in rendered
    assert "혜택" in rendered
    assert "한 판" not in rendered
    assert "회식" not in rendered
    assert "예약 문의" not in rendered


def test_selected_copy_updates_marketing_copy_and_copy_spec():
    state = _state()
    state.update(copy_candidate_generation_node(state))
    state["copy_selection"] = {"selected_copy_id": "copy_2"}
    state.update(state_update_selected_copy_node(state))
    state.update(copy_spec_parser_node(state))

    assert state["selected_copy_id"] == "copy_2"
    assert state["marketing_copy"]["headline"] == "회식은 역시 삼겹살"
    assert state["copy_spec"]["items"][0]["role"] == "headline"


def test_selected_copy_node_uses_persisted_state_selection_without_resume_payload():
    state = _state()
    state.update(copy_candidate_generation_node(state))
    state["selected_copy_id"] = "copy_2"
    state["selected_channel_id"] = "instagram-story"
    state["selected_tone"] = "깔끔한"
    state["custom_direction"] = "상품을 더 크게 보여줘"

    update = state_update_selected_copy_node(state)

    assert update["selected_copy_id"] == "copy_2"
    assert update["selected_channel_id"] == "instagram-story"
    assert update["selected_ad_format"] == "instagram_story"
    assert update["selected_tone"] == "깔끔한"
    assert update["custom_direction"] == "상품을 더 크게 보여줘"
    assert update["marketing_copy"]["headline"] == "회식은 역시 삼겹살"


def test_selected_copy_persists_frontend_choices_in_graph_state():
    state = _state()
    state.update(copy_candidate_generation_node(state))
    state["copy_selection"] = {
        "selected_copy_id": "copy_1",
        "selected_channel_id": "instagram-story",
        "selected_tone": "깔끔한",
        "custom_direction": "상품을 더 크게 보여줘",
    }

    update = state_update_selected_copy_node(state)

    assert update["selected_channel_id"] == "instagram-story"
    assert update["selected_ad_format"] == "instagram_story"
    assert update["selected_tone"] == "깔끔한"
    assert update["custom_direction"] == "상품을 더 크게 보여줘"
    assert update["context"]["brand_tone"] == "깔끔한"
    assert update["context"]["extra"]["ad_format"] == "instagram_story"
    assert update["context"]["extra"]["selected_channel_id"] == "instagram-story"
    assert update["current_brief"]["selected_channel_id"] == "instagram-story"
    assert update["current_brief"]["selected_tone"] == "깔끔한"
    assert update["current_brief"]["custom_direction"] == "상품을 더 크게 보여줘"
    assert update["ad_format_spec"]["ad_format"] == "instagram_story"
    assert update["ad_format_spec"]["height"] == 1920
    assert update["layout_spec"]["layout_type"] == "story_vertical"


def test_selected_copy_node_prefers_custom_copy_from_candidate_selection_resume():
    state = _state()
    state.update(copy_candidate_generation_node(state))
    state["copy_selection"] = {
        "selected_copy_id": "copy_2",
        "user_custom_headline": "내가 고친 삼겹살 문구",
        "user_custom_subcopy": "오늘 저녁 예약 가능",
    }

    update = state_update_selected_copy_node(state)

    assert update["selected_copy_id"] == "copy_2"
    assert update["user_custom_headline"] == "내가 고친 삼겹살 문구"
    assert update["user_custom_subcopy"] == "오늘 저녁 예약 가능"
    assert update["marketing_copy"]["headline"] == "내가 고친 삼겹살 문구"
    assert update["marketing_copy"]["subcopy"] == "오늘 저녁 예약 가능"
    assert update["marketing_copy"]["metadata"]["copy_resolution"] == "manual_edit"
