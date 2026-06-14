from orchestrator.app.graph.builder import build_marketing_graph
from orchestrator.app.graph.state import append_llm_call_result, append_model_selection, create_initial_marketing_state
from orchestrator.app.llm.adapters.mock import MockLLMAdapter
from orchestrator.app.llm.model_router import choose_model
from orchestrator.app.schemas.llm_marketing import InitialMarketingRequest


def test_initial_marketing_request_user_plan_defaults_to_free():
    request = InitialMarketingRequest(user_input="ready")
    state = create_initial_marketing_state(request)

    assert request.user_plan == "free"
    assert state["user_plan"] == "free"
    assert state["plan_policy"]["user_plan"] == "free"
    assert state["model_selections"] == []
    assert state["llm_call_results"] == []


def test_initial_marketing_request_user_plan_is_normalized():
    state = create_initial_marketing_state(InitialMarketingRequest(user_input="ready", user_plan="premium"))

    assert state["user_plan"] == "premium"
    assert state["plan_policy"]["user_plan"] == "premium"


def test_model_tracking_helpers_append_dicts():
    state = create_initial_marketing_state(InitialMarketingRequest(user_input="ready"))
    selection = choose_model("validator", "free")
    result = MockLLMAdapter().invoke_text("hello", selection)

    selection_delta = append_model_selection(state, selection)
    result_delta = append_llm_call_result(state, result)

    assert selection_delta[0]["node_name"] == "validator"
    assert result_delta[0]["success"] is True
    assert state["model_selections"] == []
    assert state["llm_call_results"] == []


def test_existing_marketing_graph_still_runs_to_result_payload():
    result = build_marketing_graph().invoke(
        {
            "user_input": "ready",
            "job_id": "model-policy-regression",
            "thread_id": "model-policy-regression",
            "copy_generation_mode": "no_copy",
            "context": {
                "business_type": "restaurant",
                "item_or_service": "BBQ",
                "promotion_goal": "reservation_cta",
                "extra": {"ad_format": "instagram_feed"},
            },
        },
        config={"configurable": {"thread_id": "model-policy-regression"}},
    )

    assert result["status"] == "done"
    assert result["user_plan"] == "free"
    assert result["plan_policy"]["user_plan"] == "free"
    assert result["result_payload"]["output_path"]
