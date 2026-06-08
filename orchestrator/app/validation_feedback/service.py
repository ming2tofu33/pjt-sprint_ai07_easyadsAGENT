"""Validation report and regeneration service."""

from __future__ import annotations

import os
from uuid import uuid4
import logging
from typing import Any

from orchestrator.app.db.session import db_transaction
from orchestrator.app.db.repositories import generation_outputs as output_repo
from orchestrator.app.db.repositories import generation_jobs as job_repo
from orchestrator.app.db.repositories import generation_job_events as event_repo
from orchestrator.app.db.repositories import chat_threads as thread_repo
from orchestrator.app.db.repositories import validation_reports as report_repo
from orchestrator.app.validation_feedback.action_mapper import build_suggested_actions, derive_scope
from orchestrator.app.validation_feedback.errors import (
    GenerationOutputNotFound,
    InvalidRegenerationAction,
    RegenerationDepthExceeded,
    RegenerationNotRecommended,
    ValidationReportNotFound,
)
from orchestrator.app.validation_feedback.failure_mapper import extract_failure_types
from orchestrator.app.validation_feedback.regeneration_policy import build_regeneration_patch
from orchestrator.app.validation_feedback.schemas import SCHEMA_VERSION, SuggestedActionCode, ValidationSummary

logger = logging.getLogger(__name__)


def build_validation_summary_from_output_row(row: dict) -> ValidationSummary:
    source_summary = normalize_validation_sources(row.get("result_payload") or {}, row.get("metadata") or {})
    failure_types = extract_failure_types(source_summary)
    actions = build_suggested_actions(failure_types)
    if not failure_types:
        status = "pass"
        decision = "pass"
    elif any(item.value in {"provider_unavailable", "manual_review_required"} for item in failure_types):
        status = "manual_review"
        decision = "manual_review"
    elif any(item.value in {"fake_text", "watermark", "unauthorized_logo", "unexpected_text", "business_fit", "visual_clutter", "commercial_viability"} for item in failure_types):
        status = "fail"
        decision = "retry_image"
    else:
        status = "fail"
        decision = "retry_layout"
    return ValidationSummary(
        status=status,
        decision=decision,
        overall_score=_score_from_sources(source_summary, failure_count=len(failure_types)),
        confidence=_confidence_from_sources(source_summary),
        failure_types=failure_types,
        suggested_actions=actions,
        source_summary=source_summary,
    )


def create_validation_report_for_output(*, public_output_id: str, workspace_id: str, created_by: str | None = None) -> dict:
    with db_transaction() as conn:
        row = output_repo.get_generation_output_by_public_id(public_output_id=public_output_id, workspace_id=workspace_id, connection=conn)
        if not row:
            raise GenerationOutputNotFound()
        if not row.get("job_id"):
            raise ValidationReportNotFound("Generation output has no source job.")
        summary = build_validation_summary_from_output_row(row)
        report = report_repo.create_validation_report(
            workspace_id=str(row["workspace_id"]),
            thread_id=str(row.get("thread_id")) if row.get("thread_id") else None,
            job_id=str(row["job_id"]),
            output_id=str(row["id"]),
            created_by=created_by,
            status=summary.status,
            decision=summary.decision,
            validation_summary=summary.model_dump(mode="json"),
            failure_types=[item.value for item in summary.failure_types],
            suggested_actions=[item.model_dump(mode="json") for item in summary.suggested_actions],
            source_reports=summary.source_summary,
            connection=conn,
        )
        output_repo.update_generation_output_validation_summary(
            output_id=str(row["id"]),
            workspace_id=str(row["workspace_id"]),
            validation_summary=_public_validation_cache(report, summary),
            connection=conn,
        )
        _safe_event(row, "validation_report_created", {"public_output_id": public_output_id, "report_id": report.get("public_validation_report_id"), "failure_type_count": len(summary.failure_types)}, connection=conn)
        return _validation_response(report, summary, public_output_id=public_output_id, public_job_id=row.get("public_job_id"))


def get_latest_validation_for_output(*, public_output_id: str, workspace_id: str) -> dict:
    row = report_repo.get_latest_validation_report_for_output(public_output_id=public_output_id, workspace_id=workspace_id)
    if not row:
        raise ValidationReportNotFound()
    return _validation_response_from_row(row)


def regenerate_output(*, public_output_id: str, workspace_id: str, suggested_actions: list[SuggestedActionCode], scope: str | None, user_instruction: str | None, idempotency_key: str) -> tuple[int, dict]:
    with db_transaction() as conn:
        output = output_repo.get_generation_output_by_public_id(public_output_id=public_output_id, workspace_id=workspace_id, connection=conn)
        if not output:
            raise GenerationOutputNotFound()
        report = report_repo.get_latest_validation_report_for_output(public_output_id=public_output_id, workspace_id=workspace_id, connection=conn)
        if not report:
            raise ValidationReportNotFound()
        existing = job_repo.get_generation_job_by_regeneration_idempotency_key(workspace_id=workspace_id, idempotency_key=idempotency_key, connection=conn)
        if existing:
            _safe_event(output, "regeneration_request_replayed", {"public_output_id": public_output_id, "depth": existing.get("regeneration_depth")}, connection=conn)
            return 200, _regeneration_response(existing, output, suggested_actions, idempotent=True)
        allowed = {item.get("code") for item in report.get("suggested_actions") or []}
        requested = [action.value if hasattr(action, "value") else str(action) for action in suggested_actions]
        if not requested:
            requested = [code for code in allowed if code != "manual_review"]
        if not requested:
            raise RegenerationNotRecommended()
        if any(action not in allowed for action in requested):
            raise InvalidRegenerationAction()
        parent_job = job_repo.get_generation_job_db_by_id(str(output["job_id"]), workspace_id=workspace_id, connection=conn)
        depth = int((parent_job or {}).get("regeneration_depth") or 0) + 1
        if depth > _max_depth():
            raise RegenerationDepthExceeded()
        patch = build_regeneration_patch(requested, scope=scope or derive_scope(requested), user_instruction=user_instruction)
        public_job_id = f"job_{uuid4().hex}"
        metadata = _regeneration_metadata(output, parent_job or {}, report, patch)
        job = job_repo.create_generation_job_row(
            public_job_id=public_job_id,
            workspace_id=workspace_id,
            thread_id=str(output.get("thread_id")) if output.get("thread_id") else None,
            requested_by=(parent_job or {}).get("requested_by"),
            status="queued",
            current_stage="queued",
            progress_percent=0,
            selected_reference_template_id=(parent_job or {}).get("selected_reference_template_id"),
            input_asset_id=(parent_job or {}).get("input_asset_id"),
            reference_asset_id=(parent_job or {}).get("reference_asset_id"),
            output_path=None,
            result_payload=None,
            error=None,
            metadata=metadata,
            run_mode=(parent_job or {}).get("run_mode") or "queued_only",
            engine=(parent_job or {}).get("engine"),
            model_provider=(parent_job or {}).get("model_provider"),
            model_name=(parent_job or {}).get("model_name"),
            prompt_preview=(parent_job or {}).get("prompt_preview"),
            brief=(parent_job or {}).get("brief") or {},
            brand_kit_snapshot=(parent_job or {}).get("brand_kit_snapshot") or {},
            params={"regeneration_patch": patch},
            request_payload={"regeneration": {"previous_output_id": public_output_id, "suggested_actions": requested}},
            parent_job_id=str(output["job_id"]),
            previous_output_id=str(output["id"]),
            regeneration_depth=depth,
            regeneration_idempotency_key=idempotency_key,
            connection=conn,
        )
        if output.get("public_thread_id"):
            thread_repo.set_chat_thread_active_job(output["public_thread_id"], active_job_id=str(job["id"]), workspace_id=workspace_id, connection=conn)
        _safe_event(output, "regeneration_requested", {"public_output_id": public_output_id, "suggested_action_codes": requested, "regeneration_scope": patch["scope"], "depth": depth}, connection=conn)
        _safe_event({**output, "job_id": job["id"]}, "regeneration_job_created", {"public_output_id": public_output_id, "public_job_id": job["public_job_id"], "depth": depth}, connection=conn)
        return 202, _regeneration_response(job, output, requested, idempotent=False)


def normalize_validation_sources(result_payload: dict, metadata: dict) -> dict[str, Any]:
    validation = result_payload.get("validation_summary") or {}
    ocr = result_payload.get("ocr_gate") or (result_payload.get("metadata") or {}).get("ocr_gate") or {}
    quality = result_payload.get("quality_gate") or (result_payload.get("metadata") or {}).get("quality_gate") or {}
    safe_area = validation.get("safe_area") or {}
    readability = validation.get("readability") or {}
    final = validation.get("final") or {}
    return {
        "decision": result_payload.get("qualityDecision") or ocr.get("decision") or quality.get("decision"),
        "ocr": {
            "backgroundDecision": (ocr.get("background") or {}).get("decision"),
            "finalDecision": (ocr.get("final") or {}).get("decision"),
            "fakeText": bool((ocr.get("background") or {}).get("fake_text") or (ocr.get("final") or {}).get("fake_text")),
            "watermark": bool((ocr.get("background") or {}).get("watermark_or_logo_text") or (ocr.get("final") or {}).get("watermark_or_logo_text")),
            "unexpectedTextCount": int((ocr.get("background") or {}).get("unexpected_text_count") or 0) + int((ocr.get("final") or {}).get("unexpected_text_count") or 0),
            "missingCopyCount": int((ocr.get("final") or {}).get("missing_text_count") or 0),
            "malformedCopyCount": int((ocr.get("final") or {}).get("malformed_text_count") or 0),
            "providerStatus": (ocr.get("background") or {}).get("status") or (ocr.get("final") or {}).get("status"),
        },
        "safeArea": {"passed": safe_area.get("overall_pass"), "score": safe_area.get("score")},
        "readability": {"passed": readability.get("overall_pass"), "score": readability.get("score"), "clipping": readability.get("text_clipping_detected")},
        "final": {"passed": final.get("overall_pass"), "contrastPassed": final.get("contrast_passed"), "clipping": final.get("text_clipping_detected")},
        "vlm": {
            "businessFitScore": quality.get("business_fit_score"),
            "commercialViabilityScore": quality.get("commercial_viability_score"),
            "visualClutterScore": quality.get("visual_clutter_score"),
        },
    }


def _public_validation_cache(report: dict, summary: ValidationSummary) -> dict:
    return {
        "reportId": report.get("public_validation_report_id"),
        "status": summary.status,
        "decision": summary.decision,
        "failureTypes": [item.value for item in summary.failure_types],
        "suggestedActions": [{"code": item.code.value, "scope": item.scope, "priority": item.priority} for item in summary.suggested_actions],
        "requiresManualReview": summary.requires_manual_review,
        "retryRecommended": summary.retry_recommended,
        "schemaVersion": SCHEMA_VERSION,
    }


def _validation_response(report: dict, summary: ValidationSummary, *, public_output_id: str, public_job_id: str | None) -> dict:
    cache = _public_validation_cache(report, summary)
    return {
        **cache,
        "outputId": public_output_id,
        "jobId": public_job_id,
        "overallScore": summary.overall_score,
        "confidence": summary.confidence,
        "suggestedActions": [item.model_dump(mode="json") for item in summary.suggested_actions],
        "createdAt": _iso(report.get("created_at")),
    }


def _validation_response_from_row(row: dict) -> dict:
    summary = row.get("validation_summary") or {}
    return {
        "reportId": row.get("public_validation_report_id"),
        "outputId": row.get("public_output_id"),
        "jobId": row.get("public_job_id"),
        "status": row.get("status"),
        "decision": row.get("decision"),
        "overallScore": summary.get("overall_score"),
        "confidence": summary.get("confidence"),
        "failureTypes": row.get("failure_types") or [],
        "suggestedActions": row.get("suggested_actions") or [],
        "retryRecommended": row.get("decision") in {"retry_image", "retry_layout", "retry_copy", "retry_full"},
        "requiresManualReview": row.get("decision") in {"manual_review", "unavailable"},
        "schemaVersion": row.get("schema_version") or SCHEMA_VERSION,
        "createdAt": _iso(row.get("created_at")),
    }


def _regeneration_response(job: dict, output: dict, actions: list[str | SuggestedActionCode], *, idempotent: bool) -> dict:
    metadata = job.get("metadata") or {}
    return {
        "jobId": job.get("public_job_id"),
        "threadId": output.get("public_thread_id") or metadata.get("public_thread_id"),
        "parentJobId": output.get("public_job_id"),
        "previousOutputId": output.get("public_output_id"),
        "depth": int(job.get("regeneration_depth") or 0),
        "status": job.get("status") or "queued",
        "appliedActions": [item.value if hasattr(item, "value") else str(item) for item in actions],
        "idempotentReplay": idempotent,
    }


def _regeneration_metadata(output: dict, parent_job: dict, report: dict, patch: dict) -> dict:
    parent_metadata = parent_job.get("metadata") or {}
    return {
        "requested_run_mode": parent_job.get("run_mode") or parent_metadata.get("requested_run_mode"),
        "effective_run_mode": parent_job.get("run_mode") or parent_metadata.get("effective_run_mode"),
        "execution_mode": "regeneration_queued",
        "public_thread_id": output.get("public_thread_id") or parent_metadata.get("public_thread_id"),
        "parent_job_id": output.get("public_job_id"),
        "previous_output_id": output.get("public_output_id"),
        "validation_report_id": report.get("public_validation_report_id"),
        "regeneration_patch": patch,
    }


def _safe_event(row: dict, event_type: str, payload: dict, *, connection: object | None = None) -> None:
    try:
        event_repo.record_generation_job_event(
            workspace_id=str(row["workspace_id"]),
            thread_id=str(row["thread_id"]),
            job_id=str(row["job_id"]),
            event_type=event_type,
            payload=payload,
            connection=connection,
        )
    except Exception:
        logger.warning("Failed to record validation feedback event.", exc_info=True)


def _score_from_sources(source_summary: dict, *, failure_count: int) -> float:
    if failure_count <= 0:
        return 1.0
    return max(0.0, round(1.0 - min(failure_count, 5) * 0.15, 2))


def _confidence_from_sources(source_summary: dict) -> float | None:
    values = []
    for section in ("safeArea", "readability"):
        value = (source_summary.get(section) or {}).get("score")
        if value is not None:
            try:
                values.append(float(value))
            except (TypeError, ValueError):
                pass
    if not values:
        return None
    return round(sum(values) / len(values), 2)


def _max_depth() -> int:
    try:
        return max(0, int(os.getenv("EASYADS_MAX_REGENERATION_DEPTH", "2")))
    except ValueError:
        return 2


def _iso(value: object) -> str | None:
    if value is None:
        return None
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return str(value)
