from orchestrator.app.quality_gate.ocr_validation import normalize_ocr_text, validate_ocr_text


def test_ocr_normalizes_korean_spacing_and_punctuation():
    assert normalize_ocr_text("딸기 라떼!") == normalize_ocr_text("딸기라떼")


def test_background_extra_text_fails():
    result = validate_ocr_text(expected_text=[], detected_text=["SALE 50%"])

    assert result.status == "fail"
    assert result.extra_text_count == 1


def test_final_copy_missing_expected_text():
    result = validate_ocr_text(expected_text=["딸기라떼 신메뉴"], detected_text=[])

    assert result.status == "fail"
    assert result.missing_text_count == 1

