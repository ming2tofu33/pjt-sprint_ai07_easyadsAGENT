"""Validation report and regeneration service."""

from __future__ import annotations

import os
from uuid import uuid4
import logging
import hashlib
import json
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
    InvalidRegenerationScope,
    RegenerationDepthExceeded,
    RegenerationIdempotencyConflict,
    RegenerationLineageConflict,
    RegenerationNotRecommended,
    OutputNotReady,
    ValidationReportNotFound,
)
from orchestrator.app.validation_feedback.failure_mapper import extract_failure_types
from orchestrator.app.validation_feedback.regeneration_policy import build_regeneration_patch
from orchestrator.app.validation_feedback.schemas import SCHEMA_VERSION, SuggestedActionCode, ValidationSummary

logger = logging.getLogger(__name__)


def build_validation_summary_from_output_row(row: dict) -> ValidationSummary:
    source_summary = normalize_validation_sources(row.get("result_payload") or {}, row.get("metadata") or {})
    if not source_summary.get("hasValidationSource"):
        unavailable_summary = {
            **source_summary,
            "decision": "unavailable",
            "ocr": {**(source_summary.get("ocr") or {}), "providerStatus": "unavailable"},
        }
        failure_types = extract_failure_types(unavailable_summary)
        actions = build_suggested_actions(failure_types)
        return ValidationSummary(
            status="unavailable",
            decision="manual_review",
            overall_score=None,
            confidence=None,
            failure_types=failure_types,
            suggested_actions=actions,
            source_summary=unavailable_summary,
        )
    failure_types = extract_failure_types(source_summary)
    actions = build_suggested_actions(failure_types)
    if not failure_types:
        status = "pass"
        decision = "pass"
    elif any(item.value in {"watermark", "unauthorized_logo"} for item in failure_types):
        status = "fail"
        decision = "reject"
    elif all(item.value in {"provider_unavailable", "manual_review_required"} for item in failure_types):
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
    event_to_record = None
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
        event_to_record = (row, "validation_report_created", {"public_output_id": public_output_id, "report_id": report.get("public_validation_report_id"), "failure_type_count": len(summary.failure_types)})
        response = _validation_response(report, summary, public_output_id=public_output_id, public_job_id=row.get("public_job_id"))
    if event_to_record:
        _safe_event(*event_to_record)
    return response


def get_latest_validation_for_output(*, public_output_id: str, workspace_id: str) -> dict:
    row = report_repo.get_latest_validation_report_for_output(public_output_id=public_output_id, workspace_id=workspace_id)
    if not row:
        raise ValidationReportNotFound()
    return _validation_response_from_row(row)


def regenerate_output(*, public_output_id: str, workspace_id: str, suggested_actions: list[SuggestedActionCode], scope: str | None, user_instruction: str | None, idempotency_key: str, requested_by: str | None = None) -> tuple[int, dict]:
    post_events: list[tuple[dict, str, dict]] = []
    with db_transaction() as conn:
        output = output_repo.get_generation_output_by_public_id(public_output_id=public_output_id, workspace_id=workspace_id, connection=conn)
        if not output:
            raise GenerationOutputNotFound()
        _validate_output_ready(output)
        report = report_repo.get_latest_validation_report_for_output(public_output_id=public_output_id, workspace_id=workspace_id, connection=conn)
        if not report:
            raise ValidationReportNotFound()
        allowed = {item.get("code") for item in report.get("suggested_actions") or []}
        requested = [action.value if hasattr(action, "value") else str(action) for action in suggested_actions]
        if "manual_review" in requested:
            raise RegenerationNotRecommended()
        if not requested:
            requested = [code for code in allowed if code != "manual_review"]
        if not requested:
            raise RegenerationNotRecommended()
        if any(action not in allowed for action in requested):
            raise InvalidRegenerationAction()
        derived_scope = derive_scope(requested)
        if scope is not None and scope != derived_scope:
            raise InvalidRegenerationScope()
        fingerprint = _request_fingerprint(public_output_id=public_output_id, actions=requested, scope=derived_scope, user_instruction=user_instruction)
        existing = job_repo.get_generation_job_by_regeneration_idempotency_key(workspace_id=workspace_id, idempotency_key=idempotency_key, connection=conn)
        if existing:
            _validate_idempotent_replay(existing, output, fingerprint)
            response = _regeneration_response(existing, output, requested, idempotent=True)
            response["_dispatch"] = None
            status_code = 200
            return status_code, response
        parent_job = job_repo.get_generation_job_db_by_id(str(output["job_id"]), workspace_id=workspace_id, connection=conn)
        if not parent_job:
            raise RegenerationLineageConflict()
        depth = int(parent_job.get("regeneration_depth") or 0) + 1
        if depth > _max_depth():
            raise RegenerationDepthExceeded()
        patch = build_regeneration_patch(requested, scope=derived_scope, user_instruction=user_instruction)
        public_job_id = f"job_{uuid4().hex}"
        metadata = _regeneration_metadata(output, parent_job, report, patch, requested_by=requested_by, fingerprint=fingerprint)
        parent_params = parent_job.get("params") or {}
        parent_request_payload = parent_job.get("request_payload") or {}
        try:
            job = job_repo.create_generation_job_row(
            public_job_id=public_job_id,
            workspace_id=workspace_id,
            thread_id=str(output.get("thread_id")) if output.get("thread_id") else None,
            requested_by=requested_by or parent_job.get("requested_by"),
            status="queued",
            current_stage="queued",
            progress_percent=0,
            selected_reference_template_id=parent_job.get("selected_reference_template_id"),
            input_asset_id=parent_job.get("input_asset_id"),
            reference_asset_id=parent_job.get("reference_asset_id"),
            output_path=None,
            result_payload=None,
            error=None,
            metadata=metadata,
            run_mode=parent_job.get("run_mode") or "queued_only",
            engine=parent_job.get("engine"),
            model_provider=parent_job.get("model_provider"),
            model_name=parent_job.get("model_name"),
            model_version=parent_job.get("model_version"),
            prompt_text=parent_job.get("prompt_text"),
            prompt_hash=parent_job.get("prompt_hash"),
            prompt_preview=parent_job.get("prompt_preview"),
            brief=parent_job.get("brief") or {},
            brand_kit_snapshot=parent_job.get("brand_kit_snapshot") or {},
            params={**parent_params, "regeneration_patch": patch},
            request_payload={**parent_request_payload, "regeneration": {"previous_output_id": public_output_id, "suggested_actions": requested, "scope": derived_scope, "fingerprint": fingerprint}},
            parent_job_id=str(output["job_id"]),
            previous_output_id=str(output["id"]),
            regeneration_depth=depth,
            regeneration_idempotency_key=idempotency_key,
            connection=conn,
            )
        except Exception:
            existing = job_repo.get_generation_job_by_regeneration_idempotency_key(workspace_id=workspace_id, idempotency_key=idempotency_key, connection=conn)
            if existing:
                _validate_idempotent_replay(existing, output, fingerprint)
                response = _regeneration_response(existing, output, requested, idempotent=True)
                response["_dispatch"] = None
                return 200, response
            raise
        if output.get("public_thread_id"):
            thread_repo.set_chat_thread_active_job(output["public_thread_id"], active_job_id=str(job["id"]), workspace_id=workspace_id, connection=conn)
        post_events.append((output, "regeneration_requested", {"public_output_id": public_output_id, "suggested_action_codes": requested, "regeneration_scope": patch["scope"], "depth": depth}))
        post_events.append(({**output, "job_id": job["id"]}, "regeneration_job_created", {"public_output_id": public_output_id, "public_job_id": job["public_job_id"], "depth": depth}))
        response = _regeneration_response(job, output, requested, idempotent=False)
        response["_dispatch"] = _dispatch_payload(job, parent_job, patch, requested_by=requested_by)
    for event in post_events:
        _safe_event(*event)
    return 202, response


def normalize_validation_sources(result_payload: dict, metadata: dict) -> dict[str, Any]:
    validation = result_payload.get("validation_summary") or metadata.get("validation_summary") or {}
    ocr = result_payload.get("ocr_gate") or (result_payload.get("metadata") or {}).get("ocr_gate") or metadata.get("ocr_gate") or {}
    quality = result_payload.get("quality_gate") or (result_payload.get("metadata") or {}).get("quality_gate") or metadata.get("quality_gate") or {}
    safe_area = validation.get("safe_area") or {}
    readability = validation.get("readability") or {}
    final = validation.get("final") or {}
    background_status = (ocr.get("background") or {}).get("status")
    final_status = (ocr.get("final") or {}).get("status")
    provider_status = _reduce_provider_status(background_status, final_status)
    has_source = bool(ocr or quality or safe_area or readability or final)
    return {
        "hasValidationSource": has_source,
        "decision": result_payload.get("qualityDecision") or ocr.get("decision") or quality.get("decision"),
        "ocr": {
            "backgroundDecision": (ocr.get("background") or {}).get("decision"),
            "finalDecision": (ocr.get("final") or {}).get("decision"),
            "backgroundProviderStatus": background_status,
            "finalProviderStatus": final_status,
            "fakeText": bool((ocr.get("background") or {}).get("fake_text") or (ocr.get("final") or {}).get("fake_text")),
            "watermark": bool((ocr.get("background") or {}).get("watermark_or_logo_text") or (ocr.get("final") or {}).get("watermark_or_logo_text")),
            "unexpectedTextCount": int((ocr.get("background") or {}).get("unexpected_text_count") or 0) + int((ocr.get("final") or {}).get("unexpected_text_count") or 0),
            "missingCopyCount": int((ocr.get("final") or {}).get("missing_text_count") or 0),
            "malformedCopyCount": int((ocr.get("final") or {}).get("malformed_text_count") or 0),
            "providerStatus": provider_status,
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


def _regeneration_metadata(output: dict, parent_job: dict, report: dict, patch: dict, *, requested_by: str | None, fingerprint: str) -> dict:
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
        "regeneration_fingerprint": fingerprint,
        "requested_by": requested_by,
        "parent_requested_by": parent_job.get("requested_by"),
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


def _dispatch_payload(job: dict, parent_job: dict, patch: dict, *, requested_by: str | None) -> dict:
    parent_request = parent_job.get("request_payload") or {}
    metadata = {**(parent_request.get("metadata") or {}), "regeneration_patch": patch}
    return {
        "jobId": job.get("public_job_id"),
        "runMode": parent_job.get("run_mode") or "queued_only",
        "request": {
            **parent_request,
            "userInput": parent_request.get("userInput") or parent_request.get("user_input") or parent_job.get("prompt_preview") or "Regenerate selected output.",
            "threadId": (job.get("metadata") or {}).get("public_thread_id"),
            "userId": requested_by or parent_job.get("requested_by"),
            "runMode": parent_job.get("run_mode") or "queued_only",
            "metadata": metadata,
        },
    }


def _validate_output_ready(output: dict) -> None:
    if output.get("output_type") not in {None, "final_image"}:
        raise OutputNotReady()
    if output.get("job_id") is None:
        raise OutputNotReady()
    if not (output.get("asset_id") or output.get("image_url") or (output.get("result_payload") or {}).get("final_image_url") or (output.get("result_payload") or {}).get("final_image_path")):
        raise OutputNotReady()


def _validate_idempotent_replay(existing: dict, output: dict, fingerprint: str) -> None:
    if str(existing.get("previous_output_id")) != str(output.get("id")):
        raise RegenerationIdempotencyConflict()
    metadata = existing.get("metadata") or {}
    if metadata.get("regeneration_fingerprint") != fingerprint:
        raise RegenerationIdempotencyConflict()


def _request_fingerprint(*, public_output_id: str, actions: list[str], scope: str, user_instruction: str | None) -> str:
    payload = {
        "outputId": public_output_id,
        "actions": sorted(actions),
        "scope": scope,
        "userInstructionHash": hashlib.sha256((user_instruction or "").encode("utf-8")).hexdigest(),
    }
    return hashlib.sha256(json.dumps(payload, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()


def _reduce_provider_status(*statuses: object) -> str | None:
    values = [str(status) for status in statuses if status]
    if not values:
        return None
    for target in ("error", "unavailable", "fail", "pass"):
        if target in values:
            return target
    return values[0]


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
