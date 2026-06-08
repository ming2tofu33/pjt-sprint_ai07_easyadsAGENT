from orchestrator.app.ocr_gate.adapters.stub import FakeOCRAdapter, StubOCRAdapter
from orchestrator.app.ocr_gate.schemas import OCRSpan, OCRValidationRequest
from orchestrator.app.ocr_gate.service import run_ocr_gate
from orchestrator.app.ocr_gate.text_normalization import normalize_ocr_text


def _span(text, confidence=0.9):
    return OCRSpan(text=text, normalized_text=normalize_ocr_text(text), confidence=confidence)


def test_background_no_text_passes():
    result = run_ocr_gate(request=OCRValidationRequest(stage="background", image_path="x.png"), adapter=FakeOCRAdapter([]))

    assert result.decision == "pass"


def test_background_sale_text_retries_image():
    result = run_ocr_gate(request=OCRValidationRequest(stage="background", image_path="x.png"), adapter=FakeOCRAdapter([_span("SALE 50%")]))

    assert result.fake_text is True
    assert result.decision == "retry_image"


def test_background_watermark_rejects():
    result = run_ocr_gate(request=OCRValidationRequest(stage="background", image_path="x.png"), adapter=FakeOCRAdapter([_span("SAMPLE")]))

    assert result.watermark_or_logo_text is True
    assert result.decision == "reject"


def test_stub_unavailable_manual_review():
    result = run_ocr_gate(request=OCRValidationRequest(stage="background", image_path="x.png"), adapter=StubOCRAdapter())

    assert result.status == "unavailable"
    assert result.decision == "manual_review"

