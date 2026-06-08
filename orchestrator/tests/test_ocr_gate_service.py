from orchestrator.app.ocr_gate.adapters.stub import FakeOCRAdapter, StubOCRAdapter
from orchestrator.app.ocr_gate.persistence import build_ocr_gate_payload, event_type_for_ocr_decision
from orchestrator.app.ocr_gate.schemas import OCRSpan, OCRValidationRequest
from orchestrator.app.ocr_gate.service import run_ocr_gate


def test_combined_payload_public_safe_summary():
    final = {"stage": "final_ad", "provider": "fake", "status": "fail", "decision": "retry_layout", "revision_action": "retry_layout", "unexpected_text": [], "expected_matches": [{}], "retry_feedback": ["bad"], "local_path": "hidden"}
    payload = build_ocr_gate_payload(final=final)

    assert payload["retry_required"] is True
    assert "local_path" not in str(payload)


def test_event_type_mapping():
    assert event_type_for_ocr_decision("retry_layout") == "ocr_gate_retry_requested"
    assert event_type_for_ocr_decision("reject") == "ocr_gate_rejected"


def test_unavailable_is_not_pass():
    result = run_ocr_gate(request=OCRValidationRequest(stage="final_ad", image_path="x.png"), adapter=StubOCRAdapter())

    assert result.decision == "manual_review"


def test_low_confidence_noise_filtered():
    result = run_ocr_gate(
        request=OCRValidationRequest(stage="background", image_path="x.png"),
        adapter=FakeOCRAdapter([OCRSpan(text="x", normalized_text="x", confidence=0.1)]),
    )

    assert result.decision == "pass"
