"""Runtime OCR gate graph node helpers."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from orchestrator.app.db.repositories import generation_job_events as generation_job_event_repo
from orchestrator.app.ocr_gate.persistence import build_ocr_event_payload, event_type_for_ocr_result
from orchestrator.app.ocr_gate.schemas import NormalizedBox, OCRValidationRequest
from orchestrator.app.ocr_gate.service import run_ocr_gate

if TYPE_CHECKING:
    from orchestrator.app.graph.state import MarketingState
else:
    MarketingState = dict


def background_ocr_gate_node(state: MarketingState) -> dict[str, Any]:
    image_path = ((state.get("t2i_result") or {}).get("image_paths") or [None])[0] or state.get("final_image_path")
    if not image_path:
        return {"ocr_gate_status": "unavailable", "ocr_gate_decision": "manual_review", "ocr_revision_action": "manual_review"}
    result = run_ocr_gate(
        request=OCRValidationRequest(
            stage="background",
            image_path=str(image_path),
            expected_text=[],
            allow_brand_text=_allowed_brand_text(state),
            business_type=_business_type(state),
            reserved_text_areas=_reserved_boxes(state),
            plan=str(state.get("user_plan") or "free"),  # type: ignore[arg-type]
        ),
        workspace_id=state.get("workspace_id"),
        created_by=state.get("user_id"),
        job_id=state.get("usage_job_db_id"),
        thread_id=state.get("usage_thread_db_id"),
    )
    payload = result.model_dump(mode="json")
    _record_event_if_possible(state, payload)
    return _state_update("background_ocr_gate", payload, state)


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
            expected_copy_required=_copy_expected_required(state),
            business_type=_business_type(state),
            reserved_text_areas=_reserved_boxes(state),
            allow_brand_text=_allowed_brand_text(state),
            plan=str(state.get("user_plan") or "free"),  # type: ignore[arg-type]
        ),
        workspace_id=state.get("workspace_id"),
        created_by=state.get("user_id"),
        job_id=state.get("usage_job_db_id"),
        thread_id=state.get("usage_thread_db_id"),
    )
    payload = result.model_dump(mode="json")
    _record_event_if_possible(state, payload)
    return _state_update("final_ocr_gate", payload, state)


def _state_update(key: str, result: dict[str, Any], state: MarketingState) -> dict[str, Any]:
    attempts = int(state.get("ocr_revision_attempts") or 0)
    if result.get("decision") in {"retry_image", "retry_layout"}:
        attempts += 1
    return {
        key: result,
        "ocr_gate_status": result.get("status"),
        "ocr_gate_decision": result.get("decision"),
        "ocr_gate_retry_feedback": result.get("retry_feedback") or [],
        "ocr_revision_action": result.get("revision_action"),
        "ocr_revision_attempts": attempts,
    }


def _record_event_if_possible(state: MarketingState, result: dict[str, Any]) -> None:
    workspace_id = state.get("workspace_id")
    thread_id = state.get("usage_thread_db_id")
    job_id = state.get("usage_job_db_id")
    if not workspace_id or not thread_id or not job_id:
        return
    try:
        generation_job_event_repo.record_generation_job_event(
            workspace_id=str(workspace_id),
            thread_id=str(thread_id),
            job_id=str(job_id),
            event_type=event_type_for_ocr_result(result),
            payload=build_ocr_event_payload(result),
        )
    except Exception:
        return


def _business_type(state: MarketingState) -> str | None:
    context = state.get("context") or {}
    return context.get("business_type") if isinstance(context, dict) else None


def _expected_copy_text(state: MarketingState) -> list[str]:
    marketing_copy = state.get("marketing_copy") if isinstance(state.get("marketing_copy"), dict) else {}
    copy_spec = state.get("copy_spec") if isinstance(state.get("copy_spec"), dict) else {}
    copy_data = {**marketing_copy, **copy_spec}
    if not isinstance(copy_data, dict):
        return []
    values = []
    for key in ("headline", "subcopy", "promotion", "cta", "brand_name"):
        value = copy_data.get(key)
        if value:
            values.append(str(value))
    return values


def _copy_expected_required(state: MarketingState) -> bool:
    if state.get("copy_generation_mode") == "no_copy" or state.get("copy_required") is False:
        return False
    return bool(state.get("copy_spec") or state.get("marketing_copy"))


def _allowed_brand_text(state: MarketingState) -> list[str]:
    context = state.get("context") if isinstance(state.get("context"), dict) else {}
    values = []
    for key in ("brand_name", "item_or_service"):
        value = context.get(key)
        if value:
            values.append(str(value))
    copy_spec = state.get("copy_spec") if isinstance(state.get("copy_spec"), dict) else {}
    brand = copy_spec.get("brand_name")
    if brand:
        values.append(str(brand))
    return values


def _reserved_boxes(state: MarketingState) -> list[NormalizedBox]:
    layout = state.get("text_layout_spec") or state.get("layout_spec") or {}
    raw_areas = layout.get("reserved_text_areas") if isinstance(layout, dict) else []
    canvas = layout.get("canvas") if isinstance(layout, dict) and isinstance(layout.get("canvas"), dict) else {}
    canvas_width = _number((canvas or {}).get("width")) or _number(layout.get("canvas_width") if isinstance(layout, dict) else None)
    canvas_height = _number((canvas or {}).get("height")) or _number(layout.get("canvas_height") if isinstance(layout, dict) else None)
    boxes: list[NormalizedBox] = []
    for area in raw_areas or []:
        box = _normalize_box(area, canvas_width=canvas_width, canvas_height=canvas_height)
        if box:
            boxes.append(box)
    return boxes


def _normalize_box(area: object, *, canvas_width: float | None, canvas_height: float | None) -> NormalizedBox | None:
    if not isinstance(area, dict):
        return None
    x1 = _number(area.get("x1", area.get("x")))
    y1 = _number(area.get("y1", area.get("y")))
    x2 = _number(area.get("x2"))
    y2 = _number(area.get("y2"))
    width = _number(area.get("width", area.get("w")))
    height = _number(area.get("height", area.get("h")))
    if x1 is None or y1 is None:
        return None
    if x2 is None and width is not None:
        x2 = x1 + width
    if y2 is None and height is not None:
        y2 = y1 + height
    if x2 is None or y2 is None:
        return None
    values = [x1, y1, x2, y2]
    if all(0 <= value <= 1 for value in values):
        scaled = [round(value * 1000) for value in values]
    elif canvas_width and canvas_height:
        scaled = [round(x1 / canvas_width * 1000), round(y1 / canvas_height * 1000), round(x2 / canvas_width * 1000), round(y2 / canvas_height * 1000)]
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
