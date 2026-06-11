from orchestrator.app.llm.nodes.quality_gate import background_quality_gate_node


def test_background_quality_gate_node_serializes_state(monkeypatch):
    monkeypatch.setenv("EASYADS_VLM_GATE_ENABLED", "false")

    update = background_quality_gate_node({"final_image_path": "x.png", "user_plan": "free"})

    assert update["background_quality_gate"]["decision"] == "unavailable"
    assert update["quality_gate_decision"] == "unavailable"

