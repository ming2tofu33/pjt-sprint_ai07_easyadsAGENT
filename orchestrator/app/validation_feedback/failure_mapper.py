"""Map public-safe validation source summaries to failure types."""

from __future__ import annotations

from orchestrator.app.validation_feedback.schemas import ValidationFailureType


ORDER = [
    ValidationFailureType.WATERMARK,
    ValidationFailureType.UNAUTHORIZED_LOGO,
    ValidationFailureType.FAKE_TEXT,
    ValidationFailureType.UNEXPECTED_TEXT,
    ValidationFailureType.COPY_MISSING,
    ValidationFailureType.COPY_MALFORMED,
    ValidationFailureType.COPY_CLIPPING,
    ValidationFailureType.COPY_SAFE_AREA,
    ValidationFailureType.COPY_UNREADABLE,
    ValidationFailureType.COPY_CONTRAST,
    ValidationFailureType.BUSINESS_FIT,
    ValidationFailureType.VISUAL_CLUTTER,
    ValidationFailureType.COMMERCIAL_VIABILITY,
    ValidationFailureType.PROVIDER_UNAVAILABLE,
    ValidationFailureType.MANUAL_REVIEW_REQUIRED,
]


def extract_failure_types(source_summary: dict) -> list[ValidationFailureType]:
    found: set[ValidationFailureType] = set()
    ocr = source_summary.get("ocr") or {}
    safe_area = source_summary.get("safeArea") or {}
    readability = source_summary.get("readability") or {}
    final = source_summary.get("final") or {}
    vlm = source_summary.get("vlm") or {}

    if ocr.get("watermark"):
        found.add(ValidationFailureType.WATERMARK)
    if ocr.get("unauthorizedLogo"):
        found.add(ValidationFailureType.UNAUTHORIZED_LOGO)
    if ocr.get("fakeText"):
        found.add(ValidationFailureType.FAKE_TEXT)
    if int(ocr.get("unexpectedTextCount") or 0) > 0:
        found.add(ValidationFailureType.UNEXPECTED_TEXT)
    if int(ocr.get("missingCopyCount") or 0) > 0:
        found.add(ValidationFailureType.COPY_MISSING)
    if int(ocr.get("malformedCopyCount") or 0) > 0:
        found.add(ValidationFailureType.COPY_MALFORMED)
    if ocr.get("providerStatus") == "unavailable":
        found.update({ValidationFailureType.PROVIDER_UNAVAILABLE, ValidationFailureType.MANUAL_REVIEW_REQUIRED})
    if safe_area.get("passed") is False:
        found.add(ValidationFailureType.COPY_SAFE_AREA)
    if readability.get("passed") is False:
        found.add(ValidationFailureType.COPY_UNREADABLE)
    if readability.get("clipping") is True or final.get("clipping") is True:
        found.add(ValidationFailureType.COPY_CLIPPING)
    if final.get("contrastPassed") is False:
        found.add(ValidationFailureType.COPY_CONTRAST)
    if _lt(vlm.get("businessFitScore"), 0.7):
        found.add(ValidationFailureType.BUSINESS_FIT)
    if _lt(vlm.get("visualClutterScore"), 0.6):
        found.add(ValidationFailureType.VISUAL_CLUTTER)
    if _lt(vlm.get("commercialViabilityScore"), 0.7):
        found.add(ValidationFailureType.COMMERCIAL_VIABILITY)
    if source_summary.get("decision") in {"manual_review", "unavailable"}:
        found.add(ValidationFailureType.MANUAL_REVIEW_REQUIRED)
    return [item for item in ORDER if item in found]


def _lt(value: object, threshold: float) -> bool:
    try:
        return float(value) < threshold
    except (TypeError, ValueError):
        return False

