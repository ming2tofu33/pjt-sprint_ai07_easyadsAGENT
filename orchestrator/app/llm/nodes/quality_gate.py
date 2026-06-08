"""Runtime quality gate graph node helpers."""

from __future__ import annotations

from typing import Any

from orchestrator.app.graph.state import MarketingState
from orchestrator.app.quality_gate.schemas import VLMQualityRequest
from orchestrator.app.quality_gate.service import run_quality_gate


def background_quality_gate_node(state: MarketingState) -> dict[str, Any]:
    image_path = state.get("final_image_path") or ((state.get("t2i_result") or {}).get("image_paths") or [None])[0]
    request = VLMQualityRequest(
        stage="background",
        business_type=((state.get("context") or {}).get("business_type") if isinstance(state.get("context"), dict) else None),
        expected_text=[],
        reserved_text_areas=_reserved_boxes(state),
        plan=str(state.get("user_plan") or "free"),  # type: ignore[arg-type]
    )
    if not image_path:
        return {"quality_gate_status": "unavailable", "quality_gate_decision": "manual_review"}
    result = run_quality_gate(
        image_path=str(image_path),
        request=request,
        workspace_id=state.get("workspace_id"),
        created_by=state.get("user_id"),
        job_id=state.get("usage_job_db_id"),
        thread_id=state.get("usage_thread_db_id"),
    )
    return {
        "background_quality_gate": result.model_dump(mode="json"),
        "quality_gate_status": result.decision,
        "quality_gate_decision": result.decision,
        "quality_gate_retry_feedback": result.retry_feedback,
        "quality_gate_attempts": int(state.get("quality_gate_attempts") or 0) + 1,
    }


def final_ad_quality_gate_node(state: MarketingState) -> dict[str, Any]:
    render_result = state.get("render_result") or {}
    image_path = render_result.get("final_image_path") if isinstance(render_result, dict) else state.get("final_image_path")
    request = VLMQualityRequest(
        stage="final_ad",
        business_type=((state.get("context") or {}).get("business_type") if isinstance(state.get("context"), dict) else None),
        expected_text=_expected_copy_text(state),
        reserved_text_areas=_reserved_boxes(state),
        plan=str(state.get("user_plan") or "free"),  # type: ignore[arg-type]
    )
    if not image_path:
        return {"quality_gate_status": "unavailable", "quality_gate_decision": "manual_review"}
    result = run_quality_gate(
        image_path=str(image_path),
        request=request,
        workspace_id=state.get("workspace_id"),
        created_by=state.get("user_id"),
        job_id=state.get("usage_job_db_id"),
        thread_id=state.get("usage_thread_db_id"),
    )
    return {
        "final_quality_gate": result.model_dump(mode="json"),
        "quality_gate_status": result.decision,
        "quality_gate_decision": result.decision,
        "quality_gate_retry_feedback": result.retry_feedback,
        "quality_gate_attempts": int(state.get("quality_gate_attempts") or 0) + 1,
    }


def _expected_copy_text(state: MarketingState) -> list[str]:
    copy_spec = state.get("copy_spec") or state.get("marketing_copy") or {}
    if not isinstance(copy_spec, dict):
        return []
    values = []
    for key in ("headline", "subcopy", "promotion", "cta", "brand_name"):
        value = copy_spec.get(key)
        if value:
            values.append(str(value))
    return values


def _reserved_boxes(state: MarketingState):
    # v1 keeps raw coordinates out of VLM if they are not already normalized.
    return []
