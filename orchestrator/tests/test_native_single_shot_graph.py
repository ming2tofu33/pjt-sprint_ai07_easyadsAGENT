from orchestrator.app.llm.nodes.creative_execution_planner import creative_execution_planner_node


def test_native_branch_plans_single_shot_without_renderer_fallback():
    update = creative_execution_planner_node({"engine": "gpt_image_2", "gpt_image2_native_single_shot": True})

    plan = update["creative_execution_plan"]
    assert plan["execution_lane"] == "gpt_native_single_shot"
    assert plan["text_rendering_mode"] == "native_typography"
    assert plan["external_renderer_fallback_allowed"] is False
