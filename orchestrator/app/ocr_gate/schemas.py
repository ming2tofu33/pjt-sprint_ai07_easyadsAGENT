"""OCR gate schemas."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, model_validator


class NormalizedBox(BaseModel):
    x1: int = Field(ge=0, le=1000)
    y1: int = Field(ge=0, le=1000)
    x2: int = Field(ge=0, le=1000)
    y2: int = Field(ge=0, le=1000)

    @model_validator(mode="after")
    def validate_order(self):
        if self.x1 >= self.x2 or self.y1 >= self.y2:
            raise ValueError("Invalid normalized box.")
        return self


class OCRSpan(BaseModel):
    text: str
    normalized_text: str
    confidence: float = Field(ge=0, le=1)
    box: NormalizedBox | None = None
    source: Literal["ocr", "vlm", "stub", "manual"] = "ocr"


class OCRExtractionResult(BaseModel):
    provider: str
    spans: list[OCRSpan] = Field(default_factory=list)
    latency_ms: int | None = None
    status: Literal["ok", "unavailable", "error"]
    error_code: str | None = None


class OCRValidationRequest(BaseModel):
    stage: Literal["background", "final_ad"]
    image_path: str
    expected_text: list[str] = Field(default_factory=list)
    business_type: str | None = None
    reserved_text_areas: list[NormalizedBox] = Field(default_factory=list)
    allow_brand_text: list[str] = Field(default_factory=list)
    plan: Literal["free", "economic", "premium"] | None = None


class OCRTextMatch(BaseModel):
    expected: str
    matched_span: OCRSpan | None = None
    similarity: float = Field(ge=0, le=1)
    status: Literal["matched", "missing", "malformed"]


class OCRValidationResult(BaseModel):
    stage: Literal["background", "final_ad"]
    provider: str
    status: Literal["pass", "fail", "manual_review", "unavailable"]
    decision: Literal["pass", "manual_review", "retry_image", "retry_layout", "reject", "unavailable"]
    detected_spans: list[OCRSpan] = Field(default_factory=list)
    expected_matches: list[OCRTextMatch] = Field(default_factory=list)
    unexpected_text: list[OCRSpan] = Field(default_factory=list)
    fake_text: bool = False
    watermark_or_logo_text: bool = False
    readability_score: float | None = Field(default=None, ge=0, le=1)
    confidence: float = Field(default=0, ge=0, le=1)
    retry_feedback: list[str] = Field(default_factory=list)
    revision_action: Literal["none", "retry_image", "retry_layout", "manual_review", "reject"] = "none"
    latency_ms: int | None = None

