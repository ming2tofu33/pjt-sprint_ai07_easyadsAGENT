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


def ocr_image_revision_node(state: MarketingState) -> dict[str, Any]:
    attempts = int(state.get("ocr_revision_attempts") or 0) + 1
    feedback = _retry_feedback(state)
    request = dict(state.get("t2i_request") or {})
    metadata = dict(request.get("metadata") or {})
    metadata.update(
        {
            "ocr_revision_attempt": attempts,
            "ocr_revision_action": "retry_image",
            "ocr_retry_feedback": feedback,
        }
    )
    request["metadata"] = metadata
    request["prompt"] = _append_once(
        request.get("prompt"),
        "text-free advertising background, no text, letters, numbers, logo, watermark, signage, or readable symbols",
    )
    request["negative_prompt"] = _append_once(
        request.get("negative_prompt"),
        "fake text, gibberish letters, watermark, logo, signage, visible writing",
    )
    if request.get("seed") is not None:
        try:
            request["seed"] = int(request["seed"]) + attempts
        except (TypeError, ValueError):
            request["seed"] = None
    return {
        "t2i_request": request,
        "ocr_revision_action": "retry_image",
        "ocr_revision_attempts": attempts,
        "ocr_gate_retry_feedback": feedback,
    }


def ocr_layout_revision_node(state: MarketingState) -> dict[str, Any]:
    attempts = int(state.get("ocr_revision_attempts") or 0) + 1
    feedback = _retry_feedback(state)
    layout = _revise_layout_dict(state.get("text_layout_spec"))
    style = _revise_style_dict(state.get("text_style_spec"))
    return {
        "text_layout_spec": layout,
        "text_style_spec": style,
        "ocr_revision_action": "retry_layout",
        "ocr_revision_attempts": attempts,
        "ocr_gate_retry_feedback": feedback,
    }


def _state_update(key: str, result: dict[str, Any], state: MarketingState) -> dict[str, Any]:
    return {
        key: result,
        "ocr_gate_status": result.get("status"),
        "ocr_gate_decision": result.get("decision"),
        "ocr_gate_retry_feedback": result.get("retry_feedback") or [],
        "ocr_revision_action": result.get("revision_action"),
        "ocr_revision_attempts": int(state.get("ocr_revision_attempts") or 0),
    }


def _retry_feedback(state: MarketingState) -> list[str]:
    feedback = state.get("ocr_gate_retry_feedback") or []
    if not feedback:
        return ["OCR gate requested revision."]
    return [str(item) for item in feedback]


def _append_once(value: object, addition: str) -> str:
    text = str(value or "").strip()
    if addition in text:
        return text
    return f"{text}, {addition}" if text else addition


def _revise_layout_dict(value: object) -> dict[str, Any]:
    layout = dict(value) if isinstance(value, dict) else {}
    layout["safe_margin_ratio"] = min(0.5, _float(layout.get("safe_margin_ratio"), 0.06) + 0.02)
    layout["ocr_revision"] = {"action": "retry_layout", "change": "expanded_text_boxes"}
    revised_slots = []
    for raw_slot in layout.get("slots") or []:
        if not isinstance(raw_slot, dict):
            revised_slots.append(raw_slot)
            continue
        slot = dict(raw_slot)
        slot["inner_padding_ratio"] = min(0.5, _float(slot.get("inner_padding_ratio"), 0.04) + 0.02)
        slot["max_lines"] = max(_int(slot.get("max_lines"), 1) + 1, 2)
        font_metric = dict(slot.get("font_metric") or {})
        if font_metric.get("base_size_ratio") is not None:
            font_metric["base_size_ratio"] = max(0.01, _float(font_metric["base_size_ratio"], 0.05) * 0.9)
        slot["font_metric"] = font_metric
        revised_slots.append(slot)
    if revised_slots:
        layout["slots"] = revised_slots
    return layout


def _revise_style_dict(value: object) -> dict[str, Any]:
    style = dict(value) if isinstance(value, dict) else {}
    typography = dict(style.get("typography") or {})
    for key in ("headline_size_ratio", "body_size_ratio"):
        if typography.get(key) is not None:
            typography[key] = max(0.01, _float(typography[key], 0.05) * 0.9)
    if typography:
        style["typography"] = typography
    style["ocr_revision"] = {"action": "retry_layout", "change": "reduced_font_scale"}
    return style


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


def _float(value: object, default: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _int(value: object, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default
