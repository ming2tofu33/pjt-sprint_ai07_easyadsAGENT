"""Aggregate OCR, VLM, and deterministic validation decisions."""

from __future__ import annotations

from pydantic import BaseModel, Field

from orchestrator.app.ocr_gate.schemas import OCRValidationResult


class RuntimeQualityDecision(BaseModel):
    decision: str
    revision_action: str
    retry_feedback: list[str] = Field(default_factory=list)
    sources: list[str] = Field(default_factory=list)


def aggregate_runtime_quality_decision(
    *,
    ocr_result: OCRValidationResult,
    vlm_result: dict | None = None,
    safe_area_report: dict | None = None,
    readability_report: dict | None = None,
) -> RuntimeQualityDecision:
    feedback = list(ocr_result.retry_feedback)
    if ocr_result.watermark_or_logo_text:
        return RuntimeQualityDecision(decision="reject", revision_action="reject", retry_feedback=feedback, sources=["ocr"])
    if ocr_result.decision in {"retry_image", "retry_layout", "reject"}:
        return RuntimeQualityDecision(decision=ocr_result.decision, revision_action=ocr_result.revision_action, retry_feedback=feedback, sources=["ocr"])
    if _vlm_failed(vlm_result):
        return RuntimeQualityDecision(decision=str(vlm_result.get("decision")), revision_action=_vlm_revision_action(vlm_result), retry_feedback=feedback + ["VLM quality gate failed."], sources=["vlm"])
    if _deterministic_failed(safe_area_report) or _deterministic_failed(readability_report):
        return RuntimeQualityDecision(decision="manual_review", revision_action="manual_review", retry_feedback=feedback + ["Deterministic validation failed."], sources=["deterministic"])
    if ocr_result.status == "unavailable" and (not vlm_result or vlm_result.get("decision") == "unavailable"):
        return RuntimeQualityDecision(decision="manual_review", revision_action="manual_review", retry_feedback=feedback + ["OCR and VLM unavailable."], sources=["ocr", "vlm"])
    return RuntimeQualityDecision(decision="pass", revision_action="none", retry_feedback=feedback, sources=["ocr"])


def _vlm_failed(result: dict | None) -> bool:
    return bool(result and result.get("decision") in {"retry", "reject", "manual_review"})


def _vlm_revision_action(result: dict | None) -> str:
    if not result:
        return "manual_review"
    if result.get("decision") == "reject":
        return "reject"
    if result.get("decision") == "retry":
        return "retry_image"
    return "manual_review"


def _deterministic_failed(report: dict | None) -> bool:
    return bool(report and report.get("overall_pass") is False)
