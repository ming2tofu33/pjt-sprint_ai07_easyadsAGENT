"""Runtime OCR validation service."""

from __future__ import annotations

import logging
from time import perf_counter

from orchestrator.app.ocr_gate import settings
from orchestrator.app.ocr_gate.adapters.base import OCRAdapter
from orchestrator.app.ocr_gate.adapters.local_http import LocalHTTPOCRAdapter
from orchestrator.app.ocr_gate.adapters.stub import StubOCRAdapter
from orchestrator.app.ocr_gate.schemas import OCRExtractionResult, OCRSpan, OCRTextMatch, OCRValidationRequest, OCRValidationResult
from orchestrator.app.ocr_gate.text_normalization import normalize_ocr_text, text_similarity
from orchestrator.app.usage import service as usage_service

logger = logging.getLogger(__name__)


def run_ocr_gate(
    *,
    request: OCRValidationRequest,
    adapter: OCRAdapter | None = None,
    workspace_id: str | None = None,
    created_by: str | None = None,
    job_id: str | None = None,
    thread_id: str | None = None,
) -> OCRValidationResult:
    started = perf_counter()
    resolved_adapter = adapter or _build_adapter()
    extraction = resolved_adapter.extract_text(image_path=request.image_path, stage=request.stage)
    result = evaluate_ocr_result(request=request, extraction=extraction, latency_ms=extraction.latency_ms or int((perf_counter() - started) * 1000))
    _record_usage_if_billable(extraction, request, workspace_id=workspace_id, created_by=created_by, job_id=job_id, thread_id=thread_id)
    return result


def evaluate_ocr_result(*, request: OCRValidationRequest, extraction: OCRExtractionResult, latency_ms: int | None = None) -> OCRValidationResult:
    if extraction.status != "ok":
        return OCRValidationResult(
            stage=request.stage,
            provider=extraction.provider,
            status="unavailable",
            decision="manual_review",
            revision_action="manual_review",
            confidence=0,
            latency_ms=latency_ms,
            retry_feedback=["OCR adapter unavailable."],
        )
    spans = [span for span in extraction.spans if span.confidence >= settings.get_min_span_confidence()]
    watermark_spans = [span for span in spans if _is_watermark(span)]
    if request.stage == "background":
        return _evaluate_background(request=request, provider=extraction.provider, spans=spans, watermark_spans=watermark_spans, latency_ms=latency_ms)
    return _evaluate_final(request=request, provider=extraction.provider, spans=spans, watermark_spans=watermark_spans, latency_ms=latency_ms)


def _evaluate_background(*, request: OCRValidationRequest, provider: str, spans: list[OCRSpan], watermark_spans: list[OCRSpan], latency_ms: int | None) -> OCRValidationResult:
    if watermark_spans:
        return OCRValidationResult(
            stage="background",
            provider=provider,
            status="fail",
            decision="reject",
            detected_spans=spans,
            unexpected_text=spans,
            fake_text=True,
            watermark_or_logo_text=True,
            confidence=max(span.confidence for span in watermark_spans),
            revision_action="reject",
            retry_feedback=["Background contains watermark/logo-like text."],
            latency_ms=latency_ms,
        )
    if spans:
        return OCRValidationResult(
            stage="background",
            provider=provider,
            status="fail",
            decision="retry_image",
            detected_spans=spans,
            unexpected_text=spans,
            fake_text=True,
            confidence=max(span.confidence for span in spans),
            revision_action="retry_image",
            retry_feedback=["Background contains unexpected readable text."],
            latency_ms=latency_ms,
        )
    return OCRValidationResult(stage="background", provider=provider, status="pass", decision="pass", confidence=1, latency_ms=latency_ms)


def _evaluate_final(*, request: OCRValidationRequest, provider: str, spans: list[OCRSpan], watermark_spans: list[OCRSpan], latency_ms: int | None) -> OCRValidationResult:
    matches = [_match_expected(expected, spans) for expected in request.expected_text]
    matched_spans = {id(match.matched_span) for match in matches if match.matched_span}
    allowed = {normalize_ocr_text(text) for text in [*request.expected_text, *request.allow_brand_text]}
    unexpected = [
        span for span in spans
        if id(span) not in matched_spans and normalize_ocr_text(span.text) not in allowed
    ]
    missing_or_bad = [match for match in matches if match.status != "matched"]
    if watermark_spans:
        return OCRValidationResult(
            stage="final_ad",
            provider=provider,
            status="fail",
            decision="reject",
            detected_spans=spans,
            expected_matches=matches,
            unexpected_text=unexpected,
            watermark_or_logo_text=True,
            confidence=max(span.confidence for span in watermark_spans),
            revision_action="reject",
            retry_feedback=["Final ad contains watermark/logo-like text."],
            latency_ms=latency_ms,
        )
    if missing_or_bad:
        return OCRValidationResult(
            stage="final_ad",
            provider=provider,
            status="fail",
            decision="retry_layout",
            detected_spans=spans,
            expected_matches=matches,
            unexpected_text=unexpected,
            confidence=max([span.confidence for span in spans] or [0]),
            revision_action="retry_layout",
            retry_feedback=["Expected copy is missing or malformed."],
            latency_ms=latency_ms,
        )
    if unexpected:
        return OCRValidationResult(
            stage="final_ad",
            provider=provider,
            status="fail",
            decision="retry_image",
            detected_spans=spans,
            expected_matches=matches,
            unexpected_text=unexpected,
            confidence=max(span.confidence for span in unexpected),
            revision_action="retry_image",
            retry_feedback=["Final ad contains unexpected extra text."],
            latency_ms=latency_ms,
        )
    return OCRValidationResult(stage="final_ad", provider=provider, status="pass", decision="pass", detected_spans=spans, expected_matches=matches, confidence=1, latency_ms=latency_ms)


def _match_expected(expected: str, spans: list[OCRSpan]) -> OCRTextMatch:
    best_span = None
    best_score = 0.0
    for span in spans:
        score = text_similarity(expected, span.text)
        if score > best_score:
            best_score = score
            best_span = span
    if best_score >= settings.get_expected_text_match_threshold():
        status = "matched"
    elif best_score >= settings.get_malformed_text_threshold():
        status = "malformed"
    else:
        status = "missing"
        best_span = None
    return OCRTextMatch(expected=expected, matched_span=best_span, similarity=best_score, status=status)


def _build_adapter() -> OCRAdapter:
    if not settings.is_ocr_gate_enabled():
        return StubOCRAdapter()
    provider = settings.get_ocr_provider()
    if provider == "local_http_ocr" and settings.is_ocr_actual_enabled():
        return LocalHTTPOCRAdapter()
    return StubOCRAdapter()


def _is_watermark(span: OCRSpan) -> bool:
    normalized = normalize_ocr_text(span.text)
    return any(term and term in normalized for term in settings.get_watermark_terms())


def _record_usage_if_billable(extraction: OCRExtractionResult, request: OCRValidationRequest, *, workspace_id: str | None, created_by: str | None, job_id: str | None, thread_id: str | None) -> None:
    if not workspace_id or extraction.provider in {"stub", "fake_test"} or extraction.status != "ok":
        return
    try:
        usage_service.record_llm_usage(
            workspace_id=workspace_id,
            provider=extraction.provider,
            model_name="ocr_adapter",
            plan=request.plan or "free",
            input_tokens=None,
            output_tokens=None,
            created_by=created_by,
            thread_id=thread_id,
            job_id=job_id,
            task_name="ocr_gate",
            node_name=f"{request.stage}_ocr_gate",
            request_status="succeeded",
        )
    except Exception:
        logger.warning("OCR usage recording failed.", exc_info=True)
