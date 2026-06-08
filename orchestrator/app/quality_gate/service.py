"""Runtime quality gate service."""

from __future__ import annotations

from time import perf_counter

from orchestrator.app.quality_gate import settings
from orchestrator.app.quality_gate.adapters.base import VLMQualityAdapter
from orchestrator.app.quality_gate.adapters.openai_compatible_vision import OpenAICompatibleVisionAdapter
from orchestrator.app.quality_gate.errors import QualityGateUnavailable
from orchestrator.app.quality_gate.ocr_validation import validate_ocr_text
from orchestrator.app.quality_gate.policy import aggregate_quality_decision, should_call_api_deep
from orchestrator.app.quality_gate.schemas import QualityCheckResult, VLMQualityGateResult, VLMQualityRequest
from orchestrator.app.usage import service as usage_service


def run_quality_gate(
    *,
    image_path: str,
    request: VLMQualityRequest,
    local_adapter: VLMQualityAdapter | None = None,
    api_adapter: VLMQualityAdapter | None = None,
    workspace_id: str | None = None,
    created_by: str | None = None,
    job_id: str | None = None,
    thread_id: str | None = None,
) -> VLMQualityGateResult:
    if not settings.is_quality_gate_enabled():
        return _unavailable_result(request, "disabled", "Quality gate is disabled.")
    started = perf_counter()
    try:
        local = local_adapter or OpenAICompatibleVisionAdapter()
        result = local.inspect(image_path=image_path, request=request)
        _safe_record_vlm_usage(result, request, workspace_id=workspace_id, created_by=created_by, job_id=job_id, thread_id=thread_id)
    except QualityGateUnavailable:
        result = _unavailable_result(request, "unavailable", "Local VLM unavailable.", latency_ms=int((perf_counter() - started) * 1000))
    if should_call_api_deep(plan=request.plan, stage=request.stage, local_result=result) and api_adapter is not None:
        try:
            api_result = api_adapter.inspect(image_path=image_path, request=request)
            _safe_record_vlm_usage(api_result, request, workspace_id=workspace_id, created_by=created_by, job_id=job_id, thread_id=thread_id)
            return aggregate_quality_decision(api_result)
        except QualityGateUnavailable:
            return result.model_copy(update={"decision": "manual_review" if result.decision == "pass" else result.decision})
    return aggregate_quality_decision(result)


def deterministic_gate(*, request: VLMQualityRequest, detected_text: list[str] | None = None) -> VLMQualityGateResult:
    ocr = validate_ocr_text(expected_text=request.expected_text, detected_text=detected_text or [])
    fake_text = QualityCheckResult(status="fail" if request.stage == "background" and ocr.extra_text_count else "pass", score=1.0 if ocr.extra_text_count else 0.0, confidence=1.0)
    result = VLMQualityGateResult(
        stage=request.stage,
        provider="deterministic",
        model_name="rule_based_v1",
        fake_text=fake_text,
        ocr=ocr,
        decision="retry" if fake_text.status == "fail" or ocr.status == "fail" else "pass",
        overall_score=0.4 if fake_text.status == "fail" else 0.9,
        confidence=1.0,
    )
    return aggregate_quality_decision(result)


def _unavailable_result(request: VLMQualityRequest, provider: str, reason: str, latency_ms: int | None = None) -> VLMQualityGateResult:
    return VLMQualityGateResult(
        stage=request.stage,
        provider=provider,
        model_name="unavailable",
        decision="manual_review" if provider != "disabled" else "unavailable",
        overall_score=0,
        confidence=0,
        retry_feedback=[reason],
        latency_ms=latency_ms,
    )


def _safe_record_vlm_usage(result: VLMQualityGateResult, request: VLMQualityRequest, *, workspace_id: str | None, created_by: str | None, job_id: str | None, thread_id: str | None) -> None:
    if not workspace_id or result.provider in {"deterministic", "disabled", "unavailable"}:
        return
    try:
        usage_service.record_llm_usage(
            workspace_id=workspace_id,
            provider=result.provider,
            model_name=result.model_name,
            plan=request.plan,
            input_tokens=None,
            output_tokens=None,
            created_by=created_by,
            thread_id=thread_id,
            job_id=job_id,
            task_name="vlm_quality_gate",
            node_name=f"{request.stage}_quality_gate",
            request_status="succeeded" if result.decision != "unavailable" else "failed",
        )
    except Exception:
        return
