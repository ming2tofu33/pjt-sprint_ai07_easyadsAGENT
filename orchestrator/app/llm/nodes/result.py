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
        metadata={
            "source_node": "result",
            "render_text_in_image": False,
            "tlfp_enabled": True,
            "error": None if output_path else upstream_error,
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
