import pytest
from pydantic import ValidationError

from orchestrator.app.ocr_gate.schemas import NormalizedBox, OCRSpan, OCRValidationResult
from orchestrator.app.ocr_gate.text_normalization import normalize_ocr_text


def test_ocr_span_and_bbox_schema():
    span = OCRSpan(text="SALE", normalized_text="sale", confidence=0.9, box=NormalizedBox(x1=1, y1=2, x2=3, y2=4))

    assert span.source == "ocr"


def test_invalid_bbox_is_rejected():
    with pytest.raises(ValidationError):
        NormalizedBox(x1=5, y1=2, x2=3, y2=4)


def test_decision_enum_rejects_unknown():
    with pytest.raises(ValidationError):
        OCRValidationResult(stage="background", provider="x", status="pass", decision="weird")


def test_raw_response_not_schema_field():
    result = OCRValidationResult(stage="background", provider="stub", status="unavailable", decision="manual_review")

    assert "raw_response" not in result.model_dump()
    assert normalize_ocr_text(" SALE 50%! ") == "sale50"

