"""Structured quality gate schemas."""

from __future__ import annotations

from typing import Any, Literal

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


class QualityRegion(BaseModel):
    label: str
    box: NormalizedBox | None = None
    confidence: float = Field(default=0.0, ge=0, le=1)
    evidence: str | None = None


class QualityCheckResult(BaseModel):
    status: Literal["pass", "fail", "unknown"] = "unknown"
    score: float = Field(default=0.0, ge=0, le=1)
    confidence: float = Field(default=0.0, ge=0, le=1)
    evidence: list[str] = Field(default_factory=list)
    regions: list[QualityRegion] = Field(default_factory=list)


class OCRSpan(BaseModel):
    text: str
    normalized_text: str
    category: Literal["matched_expected_text", "missing_expected_text", "malformed_expected_text", "unexpected_extra_text"]
    confidence: float = Field(default=0.0, ge=0, le=1)
    box: NormalizedBox | None = None


class OCRValidationResult(BaseModel):
    expected_text: list[str] = Field(default_factory=list)
    detected_text: list[str] = Field(default_factory=list)
    spans: list[OCRSpan] = Field(default_factory=list)
    status: Literal["pass", "fail", "unknown"] = "unknown"
    extra_text_count: int = 0
    missing_text_count: int = 0


class VLMQualityRequest(BaseModel):
    stage: Literal["background", "final_ad"]
    business_type: str | None = None
    expected_text: list[str] = Field(default_factory=list)
    reserved_text_areas: list[NormalizedBox] = Field(default_factory=list)
    plan: Literal["free", "economic", "premium", "internal_benchmark"] = "free"
    metadata: dict[str, Any] = Field(default_factory=dict)


class VLMQualityGateResult(BaseModel):
    stage: Literal["background", "final_ad"]
    provider: str
    model_name: str
    fake_text: QualityCheckResult = Field(default_factory=QualityCheckResult)
    unauthorized_logo: QualityCheckResult = Field(default_factory=QualityCheckResult)
    watermark: QualityCheckResult = Field(default_factory=QualityCheckResult)
    copy_safe_area: QualityCheckResult = Field(default_factory=QualityCheckResult)
    business_fit: QualityCheckResult = Field(default_factory=QualityCheckResult)
    readability: QualityCheckResult = Field(default_factory=QualityCheckResult)
    commercial_viability: QualityCheckResult = Field(default_factory=QualityCheckResult)
    ocr: OCRValidationResult = Field(default_factory=OCRValidationResult)
    decision: Literal["pass", "retry", "reject", "manual_review", "unavailable"] = "manual_review"
    overall_score: float = Field(default=0.0, ge=0, le=1)
    confidence: float = Field(default=0.0, ge=0, le=1)
    retry_feedback: list[str] = Field(default_factory=list)
    latency_ms: int | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

