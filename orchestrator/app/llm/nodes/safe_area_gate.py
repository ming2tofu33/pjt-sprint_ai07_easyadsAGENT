"""BBox-only safe area validation for TLFP."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from PIL import Image, ImageStat

from orchestrator.app.schemas.text_layout import ImageLayoutAnalysis, NormalizedBBox, SafeAreaReport, TextLayoutSpec, TextSlot
from orchestrator.app.vision.layout_analysis import bbox_overlap_ratio

if TYPE_CHECKING:
    from orchestrator.app.graph.state import MarketingState


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


def safe_area_gate_node(state: "MarketingState") -> dict[str, Any]:
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

    image_overlap = _image_layout_overlap_report(state.get("image_layout_analysis"), layout.slots, state)
    bbox_issues.extend(image_overlap["issues"])
    overlap_warnings.extend(image_overlap["warnings"])

    report = SafeAreaReport(
        overall_pass=not bbox_issues,
        reserved_text_area_count=len(reserved),
        product_overlap_warnings=overlap_warnings,
        bbox_issues=bbox_issues,
        warnings=warnings,
        metadata={
            "source_node": "safe_area_gate",
            "no_copy": no_copy,
            "actual_product_overlap": image_overlap["actual_product_overlap"],
            "face_hand_overlap": image_overlap["face_hand_overlap"],
            "ocr_artifact_overlap": image_overlap["ocr_artifact_overlap"],
            "high_saliency_overlap": image_overlap["high_saliency_overlap"],
            "contrast_risk": image_overlap["contrast_risk"],
            "layout_candidate_id": _selected_candidate_id(state),
        },
    )
    return {"safe_area_report": report.model_dump(), "status": "background_validating"}


def _image_layout_overlap_report(raw_analysis: object, slots: list[TextSlot], state: MarketingState) -> dict[str, Any]:
    report: dict[str, Any] = {
        "actual_product_overlap": 0.0,
        "face_hand_overlap": 0.0,
        "ocr_artifact_overlap": 0.0,
        "high_saliency_overlap": 0.0,
        "contrast_risk": False,
        "issues": [],
        "warnings": [],
    }
    if not raw_analysis or not slots:
        return report
    try:
        analysis = raw_analysis if isinstance(raw_analysis, ImageLayoutAnalysis) else ImageLayoutAnalysis(**raw_analysis)  # type: ignore[arg-type]
    except Exception as exc:
        report["warnings"].append(f"image_layout_analysis invalid: {exc}")
        return report

    contrast_details = _slot_contrast_details(slots, state)
    report["contrast_risk"] = any(item["fails_contrast"] for item in contrast_details)
    if contrast_details:
        report["contrast_details"] = contrast_details
    for slot in slots:
        for zone in analysis.exclusion_zones:
            overlap = bbox_overlap_ratio(slot.bbox, zone.bbox)
            if zone.zone_type == "product":
                report["actual_product_overlap"] = max(report["actual_product_overlap"], overlap)
            elif zone.zone_type in {"face", "hand", "person"}:
                report["face_hand_overlap"] = max(report["face_hand_overlap"], overlap)
            elif zone.zone_type == "ocr_artifact":
                report["ocr_artifact_overlap"] = max(report["ocr_artifact_overlap"], overlap)
            elif zone.zone_type == "high_saliency":
                report["high_saliency_overlap"] = max(report["high_saliency_overlap"], overlap)

            if _role_overlap_fails(slot.role, zone.zone_type, overlap, zone.hard_exclusion):
                report["issues"].append(f"text area overlaps {zone.zone_type} exclusion zone {zone.zone_id} by {overlap:.2f}")
            elif _role_overlap_warns(slot.role, zone.zone_type, overlap):
                report["warnings"].append(f"text area overlaps {zone.zone_type} zone {zone.zone_id} by {overlap:.2f}")
    return report


def _role_overlap_fails(role: str, zone_type: str, overlap: float, hard_exclusion: bool) -> bool:
    if zone_type == "product":
        if role == "cta":
            return overlap >= 0.03
        if role == "headline":
            return overlap >= 0.08
        return hard_exclusion and overlap >= 0.10
    if zone_type in {"face", "hand", "person"} and role in {"headline", "cta"}:
        return overlap >= 0.01
    if zone_type == "ocr_artifact":
        return overlap >= 0.01
    if zone_type == "high_saliency" and role in {"subheadline", "body"}:
        return overlap >= 0.18
    return hard_exclusion and overlap >= 0.10


def _role_overlap_warns(role: str, zone_type: str, overlap: float) -> bool:
    if zone_type == "high_saliency" and role in {"subheadline", "body"}:
        return overlap >= 0.12
    if zone_type == "product" and role == "cta":
        return overlap >= 0.01
    return overlap >= 0.18


def _slot_contrast_details(slots: list[TextSlot], state: MarketingState) -> list[dict[str, Any]]:
    result = state.get("t2i_result") or {}
    image_path = (result.get("image_paths") or [None])[0]
    if not image_path:
        return []
    details: list[dict[str, Any]] = []
    try:
        with Image.open(image_path).convert("RGB") as image:
            for slot in slots:
                bbox = slot.bbox.to_pixels(image.width, image.height)
                background_rgb = _average_region_rgb(image, bbox)
                text_rgb = _hex_to_rgb(slot.text_color)
                ratio = _contrast_ratio(background_rgb, text_rgb)
                region = image.crop((bbox[0], bbox[1], bbox[0] + max(bbox[2], 1), bbox[1] + max(bbox[3], 1))).convert("L")
                variance = float(ImageStat.Stat(region).stddev[0]) if region.size[0] and region.size[1] else 0.0
                threshold = 3.0 if slot.role == "headline" else 4.5
                fails = ratio < threshold and slot.overlay_treatment not in {"solid_panel", "gradient_panel", "blur_backdrop"}
                details.append({"slot_id": slot.slot_id, "role": slot.role, "contrast_ratio": round(ratio, 2), "background_variance": round(variance, 2), "fails_contrast": fails})
    except Exception as exc:
        details.append({"slot_id": "unknown", "role": "unknown", "contrast_ratio": 0.0, "background_variance": 0.0, "fails_contrast": True, "error": str(exc)})
    return details


def _average_region_rgb(image: Image.Image, bbox_pixels: tuple[int, int, int, int]) -> tuple[int, int, int]:
    x, y, w, h = bbox_pixels
    region = image.crop((x, y, x + max(w, 1), y + max(h, 1))).convert("RGB")
    pixels = list(region.getdata())
    if not pixels:
        return (255, 255, 255)
    count = len(pixels)
    return (sum(pixel[0] for pixel in pixels) // count, sum(pixel[1] for pixel in pixels) // count, sum(pixel[2] for pixel in pixels) // count)


def _relative_luminance(rgb: tuple[int, int, int]) -> float:
    def channel(value: int) -> float:
        normalized = value / 255
        return normalized / 12.92 if normalized <= 0.03928 else ((normalized + 0.055) / 1.055) ** 2.4

    r, g, b = (channel(component) for component in rgb)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def _contrast_ratio(first: tuple[int, int, int], second: tuple[int, int, int]) -> float:
    lum1 = _relative_luminance(first)
    lum2 = _relative_luminance(second)
    lighter = max(lum1, lum2)
    darker = min(lum1, lum2)
    return (lighter + 0.05) / (darker + 0.05)


def _hex_to_rgb(value: str) -> tuple[int, int, int]:
    cleaned = str(value or "").strip().lstrip("#")
    if len(cleaned) != 6:
        return (255, 255, 255)
    return tuple(int(cleaned[index : index + 2], 16) for index in (0, 2, 4))


def _selected_candidate_id(state: MarketingState) -> str | None:
    refinement = state.get("layout_refinement_result") or {}
    return refinement.get("selected_candidate_id") if isinstance(refinement, dict) else None
