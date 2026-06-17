from orchestrator.app.graph.nodes import state_update_node
from orchestrator.app.graph.state import create_initial_marketing_state
from orchestrator.app.schemas.llm_marketing import InitialMarketingRequest


def _state_with_selection(field, value, custom_text=None):
    state = create_initial_marketing_state(InitialMarketingRequest(user_input="광고", job_id="job-1", thread_id="thread-1"))
    state["missing_fields"] = [field]
    state["user_selection"] = {"job_id": "job-1", "thread_id": "thread-1", "field": field, "value": value, "custom_text": custom_text}
    return state


def test_state_update_applies_regular_context_value():
    state = _state_with_selection("promotion_goal", "discount_event")
    update = state_update_node(state)

    assert update["context"]["promotion_goal"] == "discount_event"
    assert "promotion_goal" not in update["missing_fields"]
    assert update["confirmed_context_fields"] == ["promotion_goal"]
    assert update["revision"] == 2


def test_state_update_maps_item_option_value_to_display_label():
    state = _state_with_selection("item_or_service", "reservation_service")
    update = state_update_node(state)

    assert update["context"]["item_or_service"] == "예약 서비스"
    assert update["context"]["extra"]["item_or_service_option_value"] == "reservation_service"
    assert update["current_brief"]["item_or_service"] == "예약 서비스"
    assert "item_or_service" not in state["current_brief"]
    assert "item_or_service" not in update["missing_fields"]


def test_state_update_applies_ad_format_to_extra_and_current_brief():
    state = _state_with_selection("ad_format", "instagram_feed")
    update = state_update_node(state)

    assert update["context"]["extra"]["ad_format"] == "instagram_feed"
    assert update["current_brief"]["requested_ad_format"] == "instagram_feed"
    assert update["confirmed_context_fields"] == ["ad_format"]
    assert state["current_brief"]["requested_ad_format"] is None


def test_state_update_handles_custom_text():
    state = _state_with_selection("business_type", "custom", "bakery")
    update = state_update_node(state)

    assert update["context"]["business_type"] == "bakery"
    assert "business_type" not in update["missing_fields"]


def test_state_update_keeps_missing_when_custom_text_is_empty():
    state = _state_with_selection("business_type", "custom")
    update = state_update_node(state)

    assert "business_type" in update["missing_fields"]


def test_state_update_accepts_usp_multi_select_list():
    state = _state_with_selection("usp", ["freshness", "value_for_money"])
    update = state_update_node(state)

    assert update["context"]["usp"] == ["freshness", "value_for_money"]


def test_state_update_records_mismatch_without_crashing():
    state = _state_with_selection("promotion_goal", "discount_event")
    state["user_selection"]["thread_id"] = "other-thread"
    update = state_update_node(state)

    assert update["status"] == "failed"
    assert "mismatch" in update["error_message"]


def test_state_update_handles_copy_generation_mode_flags():
    state = _state_with_selection("copy_generation_mode", "no_copy")

    update = state_update_node(state)

    assert update["copy_generation_mode"] == "no_copy"
    assert update["copy_required"] is False
    assert update["text_overlay_pending"] is False


def test_state_update_does_not_mutate_input_state():
    state = _state_with_selection("promotion_goal", "discount_event")
    before = {
        "current_brief": dict(state["current_brief"]),
        "messages": list(state["messages"]),
        "context": dict(state["context"]),
    }

    state_update_node(state)

    assert state["current_brief"] == before["current_brief"]
    assert state["messages"] == before["messages"]
    assert state["context"] == before["context"]


def test_state_update_does_not_append_selection_message_to_graph_transcript():
    state = _state_with_selection("promotion_goal", "discount_event")

    update = state_update_node(state)

    assert "messages" not in update
