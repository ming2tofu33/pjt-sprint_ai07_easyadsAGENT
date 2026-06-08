"""Stub and fake OCR adapters."""

from __future__ import annotations

from orchestrator.app.ocr_gate.schemas import OCRExtractionResult, OCRSpan


class StubOCRAdapter:
    provider = "stub"

    def extract_text(self, *, image_path: str, stage: str) -> OCRExtractionResult:
        return OCRExtractionResult(provider=self.provider, status="unavailable", spans=[], error_code="ocr_disabled")


class FakeOCRAdapter:
    provider = "fake_test"

    def __init__(self, spans: list[OCRSpan] | None = None, status: str = "ok") -> None:
        self.spans = list(spans or [])
        self.status = status

    def extract_text(self, *, image_path: str, stage: str) -> OCRExtractionResult:
        return OCRExtractionResult(provider=self.provider, status=self.status, spans=self.spans)

