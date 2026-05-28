"""BBox-only safe area validation for TLFP."""

from __future__ import annotations

from typing import Any

from orchestrator.app.graph.state import MarketingState
from orchestrator.app.schemas.text_layout import NormalizedBBox, SafeAreaReport, TextLayoutSpec


def bbox_iou(a: NormalizedBBox, b: NormalizedBBox) -> float:
    left = max(a.x, b.x)
    top = max(a.y, b.y)
    right = min(a.x + a.w, b.x + b.w)
    bottom = min(a.y + a.h, b.y + b.h)
    if right <= left or bottom <= top:
        return 0.0
    intersection = (right - left) * (bottom - top)
    union = a.area_ratio() + b.area_ratio() - intersection
    return intersection / union if union > 0 else 0.0


def safe_area_gate_node(state: MarketingState) -> dict[str, Any]:
    warnings: list[str] = []
    bbox_issues: list[str] = []
    overlap_warnings: list[str] = []
    no_copy = (
        state.get("copy_generation_mode") == "no_copy"
        or state.get("copy_required") is False
        or (state.get("copy_spec") or {}).get("copy_mode") == "no_copy"
    )

    layout_data = state.get("text_layout_spec") or {}
    try:
        layout = TextLayoutSpec(**layout_data)
    except Exception as exc:
        report = SafeAreaReport(
            overall_pass=False,
            reserved_text_area_count=0,
            bbox_issues=[f"text_layout_spec invalid: {exc}"],
            metadata={"source_node": "safe_area_gate"},
        )
        return {"safe_area_report": report.model_dump(), "status": "background_validating"}

    reserved = list(layout.reserved_text_areas)
    if no_copy and reserved:
        warnings.append("no_copy layout should not reserve text areas")
    if not no_copy and not reserved:
        warnings.append("text overlay workflow has no reserved text areas")

    for index, bbox in enumerate(reserved):
        try:
            NormalizedBBox(**bbox.model_dump())
        except Exception as exc:
            bbox_issues.append(f"reserved_text_areas[{index}] invalid: {exc}")

    if layout.product_zone:
        for index, bbox in enumerate(reserved):
            iou = bbox_iou(layout.product_zone, bbox)
            if iou >= 0.25:
                bbox_issues.append(f"reserved_text_areas[{index}] overlaps product_zone with IoU {iou:.2f}")
            elif iou >= 0.10:
                overlap_warnings.append(f"reserved_text_areas[{index}] overlaps product_zone with IoU {iou:.2f}")

    report = SafeAreaReport(
        overall_pass=not bbox_issues,
        reserved_text_area_count=len(reserved),
        product_overlap_warnings=overlap_warnings,
        bbox_issues=bbox_issues,
        warnings=warnings,
        metadata={"source_node": "safe_area_gate", "no_copy": no_copy},
    )
    return {"safe_area_report": report.model_dump(), "status": "background_validating"}
