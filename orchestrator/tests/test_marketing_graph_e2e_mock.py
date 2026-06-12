from pathlib import Path

from langgraph.types import Command

from orchestrator.app.graph.builder import build_intake_graph, build_marketing_graph


def test_build_intake_graph_still_interrupts_for_missing_fields():
    graph = build_intake_graph()
    result = graph.invoke(
        {"user_input": "광고 만들어줘", "thread_id": "intake-still-interrupts"},
        config={"configurable": {"thread_id": "intake-still-interrupts"}},
    )

    assert "__interrupt__" in result


def test_marketing_graph_interrupts_when_required_info_is_missing():
    graph = build_marketing_graph()
    result = graph.invoke(
        {"user_input": "광고 만들어줘", "thread_id": "marketing-missing"},
        config={"configurable": {"thread_id": "marketing-missing"}},
    )

    assert "__interrupt__" in result
    assert result["__interrupt__"][0].value["type"] == "option_question"


def test_marketing_graph_runs_to_mock_t2i_when_context_is_complete():
    graph = build_marketing_graph()
    result = graph.invoke(
        {
            "user_input": "ready",
            "job_id": "marketing-e2e-mock",
            "thread_id": "marketing-e2e-mock",
            "copy_generation_mode": "auto_pilot",
            "context": {
                "business_type": "restaurant",
                "item_or_service": "삼겹살",
                "promotion_goal": "reservation_cta",
                "extra": {"ad_format": "instagram_feed"},
            },
        },
        config={"configurable": {"thread_id": "marketing-e2e-mock"}},
    )

    assert "__interrupt__" not in result
    assert result["status"] == "done"
    for key in [
        "ad_format_spec",
        "layout_spec",
        "marketing_copy",
        "image_prompt",
        "prompt_render_output",
        "t2i_request",
        "t2i_result",
        "candidates",
    ]:
        assert result[key]
    assert result["prompt_render_output"]["engine"] == "mock"
    assert result["t2i_result"]["engine"] == "mock"
    assert len(result["t2i_result"]["image_paths"]) >= 1
    assert result["candidates"][0]["engine"] == "mock"
    image_parts = Path(result["t2i_result"]["image_paths"][0]).parts
    assert "data" in image_parts
    assert "outputs" in image_parts


def test_marketing_graph_resume_continues_to_mock_t2i():
    graph = build_marketing_graph()
    config = {"configurable": {"thread_id": "marketing-resume"}}
    interrupted = graph.invoke(
        {
            "user_input": "우리 삼겹살집 인스타 광고 문구까지 알아서",
            "job_id": "marketing-resume",
            "thread_id": "marketing-resume",
        },
        config=config,
    )
    # copy_generation_mode is now an explicit HITL choice, so the graph may interrupt for
    # more than one field. Answer each asked field until it proceeds to completion.
    resumed = interrupted
    while "__interrupt__" in resumed:
        payload = resumed["__interrupt__"][0].value
        field = payload["option_question"]["field"]
        value = "auto_pilot" if field == "copy_generation_mode" else "reservation_cta"
        resumed = graph.invoke(
            Command(
                resume={
                    "job_id": payload["job_id"],
                    "thread_id": payload["thread_id"],
                    "field": field,
                    "value": value,
                }
            ),
            config=config,
        )

    assert resumed["status"] == "done"
    assert resumed["t2i_result"]["engine"] == "mock"
    assert resumed["t2i_result"]["image_paths"]
