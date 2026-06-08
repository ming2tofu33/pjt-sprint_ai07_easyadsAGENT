from orchestrator.app.llm.nodes.ocr_gate import background_ocr_gate_node, final_ocr_gate_node
from orchestrator.app.ocr_gate.schemas import OCRValidationResult
from orchestrator.app.graph.builder import build_marketing_graph
from orchestrator.app.graph.routers import route_after_ocr_gate


def test_background_ocr_gate_state_update(monkeypatch):
    def fake_run_ocr_gate(**kwargs):
        return OCRValidationResult(stage="background", provider="stub", status="unavailable", decision="manual_review", revision_action="manual_review")

    monkeypatch.setattr("orchestrator.app.llm.nodes.ocr_gate.run_ocr_gate", fake_run_ocr_gate)
    update = background_ocr_gate_node({"t2i_result": {"image_paths": ["background.png"]}, "user_plan": "free"})

    assert update["background_ocr_gate"]["decision"] == "manual_review"
    assert update["ocr_revision_action"] == "manual_review"


def test_final_ocr_gate_collects_expected_copy(monkeypatch):
    captured = {}

    def fake_run_ocr_gate(**kwargs):
        captured["request"] = kwargs["request"]
        return OCRValidationResult(stage="final_ad", provider="fake", status="pass", decision="pass")

    monkeypatch.setattr("orchestrator.app.llm.nodes.ocr_gate.run_ocr_gate", fake_run_ocr_gate)
    update = final_ocr_gate_node({"final_image_path": "final.png", "copy_spec": {"headline": "여름 시즌 아이스라떼", "cta": "지금 주문하기"}})

    assert update["final_ocr_gate"]["decision"] == "pass"
    assert "여름 시즌 아이스라떼" in captured["request"].expected_text


def test_marketing_graph_registers_ocr_nodes():
    graph = build_marketing_graph()
    graph_data = graph.get_graph()
    node_names = {getattr(node, "id", None) for node in graph_data.nodes.values()} | set(graph_data.nodes)

    assert "background_ocr_gate" in node_names
    assert "final_ocr_gate" in node_names


def test_revision_router_respects_feature_flag(monkeypatch):
    monkeypatch.setenv("EASYADS_OCR_REVISION_LOOP_ENABLED", "false")
    assert route_after_ocr_gate({"ocr_gate_decision": "retry_image", "ocr_revision_attempts": 0}) == "continue"

    monkeypatch.setenv("EASYADS_OCR_REVISION_LOOP_ENABLED", "true")
    monkeypatch.setenv("EASYADS_OCR_MAX_REVISIONS", "1")
    assert route_after_ocr_gate({"ocr_gate_decision": "retry_image", "ocr_revision_attempts": 0}) == "t2i_revision"
    assert route_after_ocr_gate({"ocr_gate_decision": "retry_image", "ocr_revision_attempts": 1}) == "continue"


def test_ocr_node_records_public_safe_event(monkeypatch):
    calls = []

    def fake_event(**kwargs):
        calls.append(kwargs)
        return {}

    def fake_run_ocr_gate(**kwargs):
        return OCRValidationResult(stage="background", provider="fake", status="fail", decision="retry_image", revision_action="retry_image", fake_text=True)

    monkeypatch.setattr("orchestrator.app.llm.nodes.ocr_gate.generation_job_event_repo.record_generation_job_event", fake_event)
    monkeypatch.setattr("orchestrator.app.llm.nodes.ocr_gate.run_ocr_gate", fake_run_ocr_gate)

    background_ocr_gate_node({"t2i_result": {"image_paths": ["x.png"]}, "workspace_id": "w", "usage_thread_db_id": "t", "usage_job_db_id": "j"})

    assert calls[0]["event_type"] == "ocr_gate_retry_requested"
    assert "base64" not in str(calls[0]["payload"]).lower()
