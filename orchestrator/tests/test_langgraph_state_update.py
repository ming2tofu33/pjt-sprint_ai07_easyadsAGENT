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
    assert update["revision"] == 2


def test_state_update_applies_ad_format_to_extra_and_current_brief():
    state = _state_with_selection("ad_format", "instagram_feed")
    update = state_update_node(state)

    assert update["context"]["extra"]["ad_format"] == "instagram_feed"
    assert state["current_brief"]["requested_ad_format"] == "instagram_feed"


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
