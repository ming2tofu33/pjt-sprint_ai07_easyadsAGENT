"""OCR normalization and expected text validation."""

from __future__ import annotations

import re
import unicodedata

from orchestrator.app.quality_gate.schemas import OCRSpan, OCRValidationResult


def normalize_ocr_text(value: str) -> str:
    text = unicodedata.normalize("NFKC", value or "")
    text = re.sub(r"[\s\W_]+", "", text, flags=re.UNICODE)
    return text.lower()


def validate_ocr_text(*, expected_text: list[str], detected_text: list[str], confidence: float = 0.8) -> OCRValidationResult:
    expected_norm = [normalize_ocr_text(text) for text in expected_text if normalize_ocr_text(text)]
    detected_norm = [normalize_ocr_text(text) for text in detected_text if normalize_ocr_text(text)]
    spans: list[OCRSpan] = []
    matched = set()
    for original, normalized in zip(detected_text, detected_norm):
        if normalized in expected_norm:
            matched.add(normalized)
            category = "matched_expected_text"
        elif any(normalized in expected or expected in normalized for expected in expected_norm):
            category = "malformed_expected_text"
        else:
            category = "unexpected_extra_text"
        spans.append(OCRSpan(text=original, normalized_text=normalized, category=category, confidence=confidence))
    for expected in expected_norm:
        if expected not in matched and not any(expected in detected or detected in expected for detected in detected_norm):
            spans.append(OCRSpan(text=expected, normalized_text=expected, category="missing_expected_text", confidence=1.0))
    extra = sum(1 for span in spans if span.category == "unexpected_extra_text")
    missing = sum(1 for span in spans if span.category == "missing_expected_text")
    status = "pass" if extra == 0 and missing == 0 else "fail"
    return OCRValidationResult(
        expected_text=expected_text,
        detected_text=detected_text,
        spans=spans,
        status=status,
        extra_text_count=extra,
        missing_text_count=missing,
    )

