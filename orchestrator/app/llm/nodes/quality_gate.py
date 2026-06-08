"""Runtime quality gate graph node helpers."""

from __future__ import annotations

from typing import Any

from orchestrator.app.graph.state import MarketingState
from orchestrator.app.quality_gate.schemas import NormalizedBox, VLMQualityRequest
from orchestrator.app.quality_gate.service import run_quality_gate


def background_quality_gate_node(state: MarketingState) -> dict[str, Any]:
    image_path = ((state.get("t2i_result") or {}).get("image_paths") or [None])[0] or state.get("final_image_path")
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
    image_path = (render_result.get("final_image_path") if isinstance(render_result, dict) else None) or state.get("final_image_path")
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


def _reserved_boxes(state: MarketingState) -> list[NormalizedBox]:
    layout = state.get("text_layout_spec") or state.get("layout_spec") or {}
    canvas = layout.get("canvas") if isinstance(layout, dict) else {}
    canvas_width = _number((canvas or {}).get("width")) or _number(layout.get("canvas_width") if isinstance(layout, dict) else None)
    canvas_height = _number((canvas or {}).get("height")) or _number(layout.get("canvas_height") if isinstance(layout, dict) else None)
    raw_areas = layout.get("reserved_text_areas") if isinstance(layout, dict) else []
    boxes: list[NormalizedBox] = []
    for area in raw_areas or []:
        box = _normalize_box(area, canvas_width=canvas_width, canvas_height=canvas_height)
        if box is not None:
            boxes.append(box)
    return boxes


def _normalize_box(area: object, *, canvas_width: float | None, canvas_height: float | None) -> NormalizedBox | None:
    if not isinstance(area, dict):
        return None
    x = _number(area.get("x") if "x" in area else area.get("x1"))
    y = _number(area.get("y") if "y" in area else area.get("y1"))
    width = _number(area.get("w") if "w" in area else area.get("width"))
    height = _number(area.get("h") if "h" in area else area.get("height"))
    x2 = _number(area.get("x2"))
    y2 = _number(area.get("y2"))
    if x is None or y is None:
        return None
    if x2 is None:
        if width is None:
            return None
        x2 = x + width
    if y2 is None:
        if height is None:
            return None
        y2 = y + height
    values = [x, y, x2, y2]
    if all(0 <= value <= 1 for value in values):
        scaled = [round(value * 1000) for value in values]
    elif canvas_width and canvas_height and (max(x, x2) > 1000 or max(y, y2) > 1000):
        scaled = [round(x / canvas_width * 1000), round(y / canvas_height * 1000), round(x2 / canvas_width * 1000), round(y2 / canvas_height * 1000)]
    else:
        scaled = [round(value) for value in values]
    try:
        return NormalizedBox(x1=scaled[0], y1=scaled[1], x2=scaled[2], y2=scaled[3])
    except ValueError:
        return None


def _number(value: object) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
