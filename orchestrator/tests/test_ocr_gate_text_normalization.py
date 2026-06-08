from orchestrator.app.ocr_gate.text_normalization import normalize_ocr_text, text_similarity


def test_normalizes_korean_spacing_and_punctuation():
    assert normalize_ocr_text(" 여름  시즌\n아이스라떼! ") == "여름시즌아이스라떼"


def test_nfkc_and_casefold_preserve_digits():
    assert normalize_ocr_text("ＳＡＬＥ ５０％") == "sale50"


def test_similarity_threshold_helper():
    assert text_similarity("여름 시즌 아이스라떼", "여름시즌 아이스 라떼") > 0.72

