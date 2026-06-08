from orchestrator.app.llm.nodes.ocr_gate import background_ocr_gate_node, final_ocr_gate_node, ocr_image_revision_node, ocr_layout_revision_node
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
    assert "ocr_image_revision" in node_names
    assert "ocr_layout_revision" in node_names


def test_revision_router_respects_feature_flag(monkeypatch):
    monkeypatch.setenv("EASYADS_OCR_REVISION_LOOP_ENABLED", "false")
    assert route_after_ocr_gate({"ocr_gate_decision": "retry_image", "ocr_revision_attempts": 0}) == "continue"

    monkeypatch.setenv("EASYADS_OCR_GATE_ENABLED", "true")
    monkeypatch.setenv("EASYADS_OCR_REVISION_LOOP_ENABLED", "true")
    monkeypatch.setenv("EASYADS_OCR_MAX_REVISIONS", "1")
    assert route_after_ocr_gate({"ocr_gate_decision": "retry_image", "ocr_revision_attempts": 0}) == "ocr_image_revision"
    assert route_after_ocr_gate({"ocr_gate_decision": "retry_image", "ocr_revision_attempts": 1}) == "manual_review_result"
    assert route_after_ocr_gate({"ocr_gate_decision": "retry_layout", "ocr_revision_attempts": 0}) == "ocr_layout_revision"
    assert route_after_ocr_gate({"ocr_gate_decision": "reject", "ocr_revision_attempts": 0}) == "rejected_result"
    assert route_after_ocr_gate({"ocr_gate_decision": "manual_review", "ocr_revision_attempts": 0}) == "manual_review_result"


def test_ocr_revision_nodes_mutate_state():
    image_update = ocr_image_revision_node(
        {
            "ocr_revision_attempts": 0,
            "ocr_gate_retry_feedback": ["remove fake text"],
            "t2i_request": {"prompt": "premium cafe", "negative_prompt": "blur", "seed": 10},
        }
    )
    assert image_update["ocr_revision_attempts"] == 1
    assert "no text" in image_update["t2i_request"]["prompt"]
    assert image_update["t2i_request"]["seed"] == 11

    layout_update = ocr_layout_revision_node(
        {
            "ocr_revision_attempts": 0,
            "text_layout_spec": {"safe_margin_ratio": 0.06, "slots": [{"inner_padding_ratio": 0.04, "max_lines": 2, "font_metric": {"base_size_ratio": 0.08}}]},
            "text_style_spec": {"typography": {"headline_size_ratio": 0.08}},
        }
    )
    assert layout_update["ocr_revision_attempts"] == 1
    assert layout_update["text_layout_spec"]["slots"][0]["max_lines"] == 3
    assert layout_update["text_style_spec"]["typography"]["headline_size_ratio"] < 0.08


def test_result_payload_marks_ocr_terminal_quality_state():
    from orchestrator.app.llm.nodes.result import result_node

    update = result_node(
        {
            "job_id": "job",
            "thread_id": "thread",
            "t2i_result": {"image_paths": ["background.png"]},
            "copy_generation_mode": "no_copy",
            "copy_required": False,
            "background_ocr_gate": {"stage": "background", "provider": "fake", "status": "fail", "decision": "reject", "revision_action": "reject"},
        }
    )
    payload = update["result_payload"]
    assert payload["qualityDecision"] == "reject"
    assert payload["qualityRejected"] is True
    assert payload["metadata"]["qualityRejected"] is True


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
