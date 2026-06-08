from orchestrator.app.ocr_gate.adapters.stub import FakeOCRAdapter
from orchestrator.app.ocr_gate.schemas import OCRSpan, OCRValidationRequest
from orchestrator.app.ocr_gate.service import run_ocr_gate
from orchestrator.app.ocr_gate.text_normalization import normalize_ocr_text


def _span(text, confidence=0.9):
    return OCRSpan(text=text, normalized_text=normalize_ocr_text(text), confidence=confidence)


def test_final_expected_copy_matched_passes():
    request = OCRValidationRequest(stage="final_ad", image_path="x.png", expected_text=["여름 시즌 아이스라떼", "지금 주문하기"])

    result = run_ocr_gate(request=request, adapter=FakeOCRAdapter([_span("여름 시즌 아이스라떼"), _span("지금 주문하기")]))

    assert result.decision == "pass"


def test_final_missing_copy_retries_layout():
    request = OCRValidationRequest(stage="final_ad", image_path="x.png", expected_text=["여름 시즌 아이스라떼"])

    result = run_ocr_gate(request=request, adapter=FakeOCRAdapter([]))

    assert result.decision == "retry_layout"


def test_final_unexpected_extra_retries_image():
    request = OCRValidationRequest(stage="final_ad", image_path="x.png", expected_text=["여름 시즌 아이스라떼"])

    result = run_ocr_gate(request=request, adapter=FakeOCRAdapter([_span("여름 시즌 아이스라떼"), _span("SALE")]))

    assert result.decision == "retry_image"


def test_final_watermark_rejects():
    request = OCRValidationRequest(stage="final_ad", image_path="x.png", expected_text=["여름 시즌 아이스라떼"])

    result = run_ocr_gate(request=request, adapter=FakeOCRAdapter([_span("여름 시즌 아이스라떼"), _span("shutterstock")]))

    assert result.decision == "reject"

