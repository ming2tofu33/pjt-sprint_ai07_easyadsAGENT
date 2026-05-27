from pathlib import Path

from orchestrator.app.graph.builder import build_marketing_graph


def test_marketing_graph_runs_tlfp_to_mock_t2i():
    graph = build_marketing_graph()
    result = graph.invoke(
        {
            "user_input": "ready",
            "job_id": "marketing-tlfp-mock",
            "thread_id": "marketing-tlfp-mock",
            "copy_generation_mode": "auto_pilot",
            "context": {
                "business_type": "restaurant",
                "item_or_service": "삼겹살",
                "promotion_goal": "reservation_cta",
                "extra": {"ad_format": "instagram_feed"},
            },
        },
        config={"configurable": {"thread_id": "marketing-tlfp-mock"}},
    )

    assert result["status"] == "done"
    for key in ["copy_spec", "text_layout_spec", "text_style_spec", "image_prompt_spec", "t2i_result"]:
        assert result[key]
    assert result["prompt_render_output"]["metadata"]["tlfp_enabled"] is True
    assert result["t2i_request"]["metadata"]["tlfp_enabled"] is True
    assert result["t2i_request"]["metadata"]["text_layout_spec"]
    assert result["t2i_request"]["metadata"]["image_prompt_spec"]
    assert result["t2i_request"]["metadata"]["render_text_in_image"] is False
    assert result["t2i_result"]["engine"] == "mock"
    image_path = Path(result["t2i_result"]["image_paths"][0])
    assert "data" in image_path.parts
    assert "outputs" in image_path.parts


def test_tlfp_image_prompt_spec_takes_priority_over_legacy_image_prompt():
    graph = build_marketing_graph()
    result = graph.invoke(
        {
            "user_input": "ready",
            "job_id": "marketing-tlfp-priority",
            "thread_id": "marketing-tlfp-priority",
            "copy_generation_mode": "auto_pilot",
            "context": {
                "business_type": "restaurant",
                "item_or_service": "삼겹살",
                "promotion_goal": "reservation_cta",
                "extra": {"ad_format": "instagram_feed"},
            },
        },
        config={"configurable": {"thread_id": "marketing-tlfp-priority"}},
    )

    assert result["image_prompt_spec"]["positive_prompt_en"] == result["t2i_request"]["prompt"]
    assert result["image_prompt_spec"]["negative_prompt_en"] == result["t2i_request"]["negative_prompt"]
