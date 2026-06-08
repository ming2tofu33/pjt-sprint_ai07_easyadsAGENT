from orchestrator.app.ocr_gate.adapters.stub import FakeOCRAdapter, StubOCRAdapter
from orchestrator.app.ocr_gate.persistence import build_ocr_gate_payload, event_type_for_ocr_decision
from orchestrator.app.ocr_gate.schemas import OCRSpan, OCRValidationRequest
from orchestrator.app.ocr_gate.runtime_quality import aggregate_runtime_quality_decision
from orchestrator.app.ocr_gate.service import run_ocr_gate


def test_combined_payload_public_safe_summary():
    final = {"stage": "final_ad", "provider": "fake", "status": "fail", "decision": "retry_layout", "revision_action": "retry_layout", "unexpected_text": [], "expected_matches": [{}], "retry_feedback": ["bad"], "local_path": "hidden"}
    payload = build_ocr_gate_payload(final=final)

    assert payload["retry_required"] is True
    assert "local_path" not in str(payload)


def test_event_type_mapping():
    assert event_type_for_ocr_decision("retry_layout") == "ocr_gate_retry_requested"
    assert event_type_for_ocr_decision("reject") == "ocr_gate_rejected"
    assert event_type_for_ocr_decision("weird") == "ocr_gate_unavailable"


def test_unavailable_is_not_pass():
    result = run_ocr_gate(request=OCRValidationRequest(stage="final_ad", image_path="x.png"), adapter=StubOCRAdapter())

    assert result.decision == "manual_review"


def test_low_confidence_noise_filtered():
    result = run_ocr_gate(
        request=OCRValidationRequest(stage="background", image_path="x.png"),
        adapter=FakeOCRAdapter([OCRSpan(text="x", normalized_text="x", confidence=0.1)]),
    )

    assert result.decision == "pass"


def test_runtime_quality_rejects_ocr_watermark():
    ocr = run_ocr_gate(request=OCRValidationRequest(stage="background", image_path="x.png"), adapter=FakeOCRAdapter([OCRSpan(text="SAMPLE", normalized_text="sample", confidence=0.9)]))

    decision = aggregate_runtime_quality_decision(ocr_result=ocr, vlm_result={"decision": "pass"})

    assert decision.decision == "reject"


def test_runtime_quality_manual_when_ocr_and_vlm_unavailable():
    ocr = run_ocr_gate(request=OCRValidationRequest(stage="background", image_path="x.png"), adapter=StubOCRAdapter())

    decision = aggregate_runtime_quality_decision(ocr_result=ocr, vlm_result={"decision": "unavailable"})

    assert decision.decision == "manual_review"


def test_thresholds_are_clamped(monkeypatch):
    from orchestrator.app.ocr_gate import settings

    monkeypatch.setenv("EASYADS_OCR_EXPECTED_TEXT_MATCH_THRESHOLD", "2")
    monkeypatch.setenv("EASYADS_OCR_MALFORMED_TEXT_THRESHOLD", "3")
    monkeypatch.setenv("EASYADS_OCR_MIN_SPAN_CONFIDENCE", "-1")

    assert settings.get_expected_text_match_threshold() == 1.0
    assert settings.get_malformed_text_threshold() == 1.0
    assert settings.get_min_span_confidence() == 0.0


def test_local_http_provider_enabled_without_ocr_actual(monkeypatch):
    from orchestrator.app.ocr_gate.service import _build_adapter

    monkeypatch.setenv("EASYADS_OCR_GATE_ENABLED", "true")
    monkeypatch.setenv("EASYADS_OCR_PROVIDER", "local_http_ocr")
    monkeypatch.delenv("EASYADS_OCR_ACTUAL", raising=False)

    assert _build_adapter().provider == "local_http_ocr"


def test_unknown_provider_falls_back_to_stub(monkeypatch):
    from orchestrator.app.ocr_gate.service import _build_adapter

    monkeypatch.setenv("EASYADS_OCR_GATE_ENABLED", "true")
    monkeypatch.setenv("EASYADS_OCR_PROVIDER", "weird")

    assert _build_adapter().provider == "stub"
