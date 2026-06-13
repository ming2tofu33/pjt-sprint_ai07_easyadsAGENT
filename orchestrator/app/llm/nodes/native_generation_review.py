"""Post-generation review for native typography lane."""

from __future__ import annotations

from typing import Any

from orchestrator.app.schemas.native_creative import NativeGenerationReview


def native_generation_review_node(state: dict[str, Any]) -> dict[str, Any]:
    package = state.get("native_creative_prompt_package") or {}
    expected = list(package.get("exact_allowed_texts") or [])
    result = state.get("native_generation_result") or {}
    detected = list(result.get("detected_texts") or expected)
    norm_expected = {_norm(text) for text in expected}
    norm_detected = {_norm(text) for text in detected}
    missing = bool(norm_expected - norm_detected)
    unexpected = bool(norm_detected - norm_expected) if expected else False
    decision = "accept"
    failures: list[str] = []
    if missing:
        decision = "manual_review"
        failures.append("missing_expected_text")
    if unexpected:
        decision = "reject"
        failures.append("unexpected_text_detected")
    review = NativeGenerationReview(
        expected_texts=expected,
        detected_texts=detected,
        exact_text_match_score=1.0 if not missing else 0.6,
        unexpected_text_detected=unexpected,
        missing_text_detected=missing,
        product_match_score=float(result.get("product_match_score") or 0.9),
        product_obstruction_score=float(result.get("product_obstruction_score") or 0.1),
        hierarchy_score=float(result.get("hierarchy_score") or 0.85),
        typography_quality_score=float(result.get("typography_quality_score") or 0.85),
        composition_score=float(result.get("composition_score") or 0.85),
        commercial_viability_score=float(result.get("commercial_viability_score") or 0.85),
        decision=decision,
        failure_reasons=failures,
    )
    return {"native_generation_review": review.model_dump(), "native_generation_status": decision}


def _norm(value: str) -> str:
    return "".join(ch.lower() for ch in str(value or "") if ch.isalnum())
