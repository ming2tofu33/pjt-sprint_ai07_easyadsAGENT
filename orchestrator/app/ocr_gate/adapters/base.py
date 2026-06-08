"""OCR adapter protocol."""

from __future__ import annotations

from typing import Protocol

from orchestrator.app.ocr_gate.schemas import OCRExtractionResult


class OCRAdapter(Protocol):
    provider: str

    def extract_text(self, *, image_path: str, stage: str) -> OCRExtractionResult:
        ...

