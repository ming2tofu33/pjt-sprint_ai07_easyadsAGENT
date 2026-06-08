"""Runtime OCR gate graph node helpers."""

from __future__ import annotations

from typing import Any

from orchestrator.app.graph.state import MarketingState
from orchestrator.app.ocr_gate.schemas import OCRValidationRequest
from orchestrator.app.ocr_gate.service import run_ocr_gate
from orchestrator.app.quality_gate.schemas import NormalizedBox


def background_ocr_gate_node(state: MarketingState) -> dict[str, Any]:
    image_path = ((state.get("t2i_result") or {}).get("image_paths") or [None])[0] or state.get("final_image_path")
    if not image_path:
        return {"ocr_gate_status": "unavailable", "ocr_gate_decision": "manual_review", "ocr_revision_action": "manual_review"}
    result = run_ocr_gate(
        request=OCRValidationRequest(
            stage="background",
            image_path=str(image_path),
            expected_text=[],
            business_type=_business_type(state),
            reserved_text_areas=_reserved_boxes(state),
            plan=str(state.get("user_plan") or "free"),  # type: ignore[arg-type]
        ),
        workspace_id=state.get("workspace_id"),
        created_by=state.get("user_id"),
        job_id=state.get("usage_job_db_id"),
        thread_id=state.get("usage_thread_db_id"),
    )
    return _state_update("background_ocr_gate", result.model_dump(mode="json"), state)


def final_ocr_gate_node(state: MarketingState) -> dict[str, Any]:
    render_result = state.get("render_result") or {}
    image_path = (render_result.get("final_image_path") if isinstance(render_result, dict) else None) or state.get("final_image_path")
    if not image_path:
        return {"ocr_gate_status": "unavailable", "ocr_gate_decision": "manual_review", "ocr_revision_action": "manual_review"}
    result = run_ocr_gate(
        request=OCRValidationRequest(
            stage="final_ad",
            image_path=str(image_path),
            expected_text=_expected_copy_text(state),
            business_type=_business_type(state),
            reserved_text_areas=_reserved_boxes(state),
            plan=str(state.get("user_plan") or "free"),  # type: ignore[arg-type]
        ),
        workspace_id=state.get("workspace_id"),
        created_by=state.get("user_id"),
        job_id=state.get("usage_job_db_id"),
        thread_id=state.get("usage_thread_db_id"),
    )
    return _state_update("final_ocr_gate", result.model_dump(mode="json"), state)


def _state_update(key: str, result: dict[str, Any], state: MarketingState) -> dict[str, Any]:
    return {
        key: result,
        "ocr_gate_status": result.get("status"),
        "ocr_gate_decision": result.get("decision"),
        "ocr_gate_retry_feedback": result.get("retry_feedback") or [],
        "ocr_revision_action": result.get("revision_action"),
        "ocr_revision_attempts": int(state.get("ocr_revision_attempts") or 0),
    }


def _business_type(state: MarketingState) -> str | None:
    context = state.get("context") or {}
    return context.get("business_type") if isinstance(context, dict) else None


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


def _reserved_boxes(state: MarketingState) -> list[NormalizedBox]:
    layout = state.get("text_layout_spec") or state.get("layout_spec") or {}
    raw_areas = layout.get("reserved_text_areas") if isinstance(layout, dict) else []
    boxes: list[NormalizedBox] = []
    for area in raw_areas or []:
        if not isinstance(area, dict):
            continue
        try:
            values = {key: int(round(float(area[key]) * 1000 if 0 <= float(area[key]) <= 1 else float(area[key]))) for key in ("x1", "y1", "x2", "y2") if key in area}
            if len(values) == 4:
                boxes.append(NormalizedBox(**values))
        except Exception:
            continue
    return boxes
