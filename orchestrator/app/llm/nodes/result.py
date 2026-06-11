"""Final result payload node for TLFP graphs."""

from __future__ import annotations

from typing import Any

from orchestrator.app.graph.state import MarketingState
from orchestrator.app.ocr_gate.persistence import build_ocr_gate_payload
from orchestrator.app.schemas.text_layout import ResultPayload


def result_node(state: MarketingState) -> dict[str, Any]:
    t2i_result = state.get("t2i_result") or {}
    background_path = (t2i_result.get("image_paths") or [None])[0]
    upstream_error = t2i_result.get("error") or state.get("error_message") or "missing output path"
    no_copy = (
        state.get("copy_generation_mode") == "no_copy"
        or state.get("copy_required") is False
        or (state.get("copy_spec") or {}).get("copy_mode") == "no_copy"
    )
    if no_copy:
        output_path = background_path
        final_image_path = state.get("final_image_path") if state.get("final_image_path") != background_path else None
        has_text_overlay = False
    else:
        output_path = state.get("final_image_path")
        final_image_path = state.get("final_image_path")
        has_text_overlay = bool(output_path)

    status = "done" if output_path else "failed"
    render_result = state.get("render_result") or {}
    render_metadata = dict(render_result.get("metadata") or {})
    result_metadata = {
        "source_node": "result",
        "render_text_in_image": False,
        "tlfp_enabled": True,
        "error": None if output_path else upstream_error,
    }
    if render_metadata:
        result_metadata["render_metadata"] = render_metadata
    artifacts = list(state.get("artifact_refs") or [])
    if output_path:
        artifacts.append(
            {
                "type": "result_image",
                "path": output_path,
                "metadata": {"source": "result_node", "has_text_overlay": has_text_overlay},
            }
        )

    ocr_gate_payload = build_ocr_gate_payload(
        background=state.get("background_ocr_gate"),
        final=state.get("final_ocr_gate"),
    )
    ocr_decision = ocr_gate_payload.get("decision")
    requires_manual_review = ocr_decision in {"manual_review", "unavailable"} or (
        ocr_decision in {"retry_image", "retry_layout"} and bool(state.get("ocr_revision_attempts"))
    )
    quality_rejected = ocr_decision == "reject"
    payload = ResultPayload(
        job_id=str(state.get("job_id") or ""),
        thread_id=str(state.get("thread_id") or ""),
        status=status,
        output_path=output_path,
        background_image_path=background_path,
        final_image_path=final_image_path,
        copy_generation_mode=state.get("copy_generation_mode"),
        has_text_overlay=has_text_overlay,
        validation_summary={
            "background": state.get("background_validation_report"),
            "safe_area": state.get("safe_area_report"),
            "readability": state.get("readability_report"),
            "final": state.get("final_validation_report"),
        },
        artifact_refs=artifacts,
        compliance=_build_copy_compliance_payload(state),
        metadata={
            **result_metadata,
            "ocr_gate": ocr_gate_payload,
            "requiresManualReview": requires_manual_review,
            "qualityRejected": quality_rejected,
            "qualityDecision": ocr_decision,
        },
    )
    payload_dict = payload.model_dump()
    payload_dict["ocr_gate"] = ocr_gate_payload
    payload_dict["qualityDecision"] = ocr_decision
    payload_dict["requiresManualReview"] = requires_manual_review
    payload_dict["qualityRejected"] = quality_rejected
    return {
        "result_payload": payload_dict,
        "artifact_refs": artifacts,
        "status": status,
        "error_message": None if output_path else upstream_error,
    }


def _build_copy_compliance_payload(state: MarketingState) -> dict:
    gate = state.get("copy_compliance_gate") or {}
    status = state.get("copy_compliance_status") or "pass"
    publication_ready = state.get("copy_compliance_publication_ready", True)

    findings_raw = gate.get("findings") or []
    findings = [
        {
            "findingId": f.get("finding_id"),
            "field": f.get("field"),
            "matchedText": f.get("matched_text"),
            "severity": f.get("severity"),
            "detectionMethod": f.get("detection_method", "pattern"),
            "confidence": f.get("confidence", 1.0),
            "message": f.get("reason"),
            "legalBasis": [
                {
                    "key": b.get("key"),
                    "lawName": b.get("law_name"),
                    "article": b.get("article"),
                    "summary": b.get("summary"),
                }
                for b in (f.get("legal_basis") or [])
            ],
            "suggestedText": f.get("suggested_text"),
            "ragContext": f.get("rag_context"),
        }
        for f in findings_raw
    ]

    if status == "pass":
        summary = "광고 규제 검토를 통과했습니다."
    elif status == "warn":
        summary = f"광고 규제 주의 표현 {len(findings)}개가 발견되었습니다. 게시 가능합니다."
    elif status == "manual_review_required":
        summary = "광고 규제 위험 표현이 발견되었습니다. 게시 전 확인이 필요합니다."
    else:
        summary = f"광고 규제 위험 표현 {len(findings)}개가 발견되었습니다."

    return {
        "status": status,
        "publicationReady": publication_ready,
        "summary": summary,
        "findingCount": len(findings),
        "findings": findings,
        "userDecision": gate.get("user_decision"),
        "userAcknowledgedRisk": gate.get("user_acknowledged_risk", False),
    }
