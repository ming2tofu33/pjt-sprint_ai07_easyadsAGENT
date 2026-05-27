from orchestrator.app.graph.nodes import input_node
from orchestrator.app.graph.state import create_initial_marketing_state
from orchestrator.app.schemas.llm_marketing import InitialMarketingRequest


def test_initial_request_and_marketing_state_exist():
    request = InitialMarketingRequest(user_input="우리 삼겹살집 인스타 광고")
    state = create_initial_marketing_state(request)

    assert state["job_id"].startswith("job_")
    assert state["thread_id"].startswith("thread_")
    assert state["status"] == "input_received"
    assert state["entry_mode"] == "chat_start"
    assert state["generation_route"] == "text_to_image"
    assert state["render_profile"] == "balanced"
    assert state["messages"][0]["content"] == request.user_input


def test_initial_state_preserves_external_thread_id():
    request = InitialMarketingRequest(user_input="카페 광고", job_id="job-x", thread_id="thread-x")
    state = create_initial_marketing_state(request)

    assert state["job_id"] == "job-x"
    assert state["thread_id"] == "thread-x"


def test_input_node_does_not_reinitialize_existing_state():
    state = create_initial_marketing_state(InitialMarketingRequest(user_input="카페 광고"))
    state["revision"] = 9

    result = input_node(state)

    assert result["revision"] == 9
    assert result["job_id"] == state["job_id"]


def test_calculate_dirty_fields_propagates_tlfp_specs():
    from orchestrator.app.graph.state import calculate_dirty_fields

    dirty = calculate_dirty_fields({}, ["brand_tone", "ad_format", "price_or_discount"])

    assert "text_style_spec" in dirty
    assert "text_layout_spec" in dirty
    assert "image_prompt_spec" in dirty
    assert "prompt_render_output" in dirty
    assert "t2i_request" in dirty
