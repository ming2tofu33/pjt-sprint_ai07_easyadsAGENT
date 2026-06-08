from orchestrator.app.llm.nodes.ocr_gate import background_ocr_gate_node, final_ocr_gate_node
from orchestrator.app.ocr_gate.schemas import OCRValidationResult


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

