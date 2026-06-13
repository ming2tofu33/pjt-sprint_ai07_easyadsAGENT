from orchestrator.app.ocr_gate.schemas import NormalizedBox, OCRSpan, OCRValidationResult
from orchestrator.app.ocr_gate.text_normalization import normalize_ocr_text


def make_ocr_span(text: str, *, confidence: float = 0.9, box: NormalizedBox | None = None) -> OCRSpan:
    return OCRSpan(
        text=text,
        normalized_text=normalize_ocr_text(text),
        confidence=confidence,
        box=box,
    )


def make_normalized_box(x1: float, y1: float, x2: float, y2: float) -> NormalizedBox:
    return NormalizedBox(x1=x1, y1=y1, x2=x2, y2=y2)


def make_ocr_validation_result(
    *,
    stage: str = "background",
    provider: str = "fake",
    status: str = "pass",
    decision: str = "pass",
    revision_action: str | None = "none",
    **overrides,
) -> OCRValidationResult:
    return OCRValidationResult(
        stage=stage,
        provider=provider,
        status=status,
        decision=decision,
        revision_action=revision_action,
        **overrides,
    )
