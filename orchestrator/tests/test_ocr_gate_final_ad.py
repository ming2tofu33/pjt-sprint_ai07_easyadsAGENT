from orchestrator.app.ocr_gate.adapters.stub import FakeOCRAdapter
from orchestrator.app.ocr_gate.schemas import NormalizedBox, OCRSpan, OCRValidationRequest
from orchestrator.app.ocr_gate.service import run_ocr_gate
from orchestrator.app.ocr_gate.text_normalization import normalize_ocr_text


def _span(text, confidence=0.9):
    return OCRSpan(text=text, normalized_text=normalize_ocr_text(text), confidence=confidence)


def _boxed_span(text, x1, y1, x2, y2, confidence=0.9):
    return OCRSpan(text=text, normalized_text=normalize_ocr_text(text), confidence=confidence, box=NormalizedBox(x1=x1, y1=y1, x2=x2, y2=y2))


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


def test_expected_copy_can_match_split_ocr_spans():
    request = OCRValidationRequest(stage="final_ad", image_path="x.png", expected_text=["여름 시즌 아이스라떼"])

    result = run_ocr_gate(request=request, adapter=FakeOCRAdapter([_boxed_span("여름 시즌", 10, 10, 200, 80), _boxed_span("아이스라떼", 210, 10, 400, 80)]))

    assert result.decision == "pass"


def test_expected_copy_required_empty_text_manual_review():
    request = OCRValidationRequest(stage="final_ad", image_path="x.png", expected_text=[], expected_copy_required=True)

    result = run_ocr_gate(request=request, adapter=FakeOCRAdapter([]))

    assert result.decision == "manual_review"


def test_unexpected_text_priority_over_missing_copy():
    request = OCRValidationRequest(stage="final_ad", image_path="x.png", expected_text=["여름 시즌 아이스라떼"])

    result = run_ocr_gate(request=request, adapter=FakeOCRAdapter([_span("SALE")]))

    assert result.decision == "retry_image"
