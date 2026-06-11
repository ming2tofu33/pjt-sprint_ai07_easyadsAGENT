"""Quality gate aggregation policy."""

from __future__ import annotations

from orchestrator.app.quality_gate import settings
from orchestrator.app.quality_gate.schemas import VLMQualityGateResult


def aggregate_quality_decision(result: VLMQualityGateResult) -> VLMQualityGateResult:
    feedback: list[str] = list(result.retry_feedback)
    decision = result.decision
    if result.watermark.status == "fail" and result.watermark.score >= settings.env_float("EASYADS_VLM_WATERMARK_THRESHOLD", 0.85):
        decision = "reject"
        feedback.append("Remove visible watermark.")
    elif result.fake_text.status == "fail" and result.stage == "background":
        decision = "retry"
        feedback.append("Regenerate background without readable text.")
    elif result.copy_safe_area.status == "fail":
        decision = "retry"
        feedback.append("Preserve the reserved copy safe area.")
    elif result.business_fit.status == "fail" or result.commercial_viability.status == "fail":
        decision = "manual_review" if result.confidence < settings.env_float("EASYADS_VLM_AMBIGUOUS_CONFIDENCE", 0.75) else "reject"
    elif result.ocr.status == "fail":
        decision = "retry" if result.stage == "final_ad" else "retry"
        feedback.append("Resolve OCR text mismatch.")
    elif result.confidence < settings.env_float("EASYADS_VLM_AMBIGUOUS_CONFIDENCE", 0.75):
        decision = "manual_review"
    elif decision not in {"reject", "retry", "manual_review", "unavailable"}:
        decision = "pass"
    return result.model_copy(update={"decision": decision, "retry_feedback": feedback})


def should_call_api_deep(*, plan: str, stage: str, local_result: VLMQualityGateResult) -> bool:
    if plan == "free":
        return False
    if plan == "premium":
        return True
    return local_result.decision in {"manual_review", "retry"} or local_result.confidence < 0.75

