"""Rule-based readability gate for rendered TLFP images."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from PIL import Image

from orchestrator.app.llm.nodes.safe_area_gate import bbox_iou
from orchestrator.app.llm.nodes.text_renderer import hex_to_rgb
from orchestrator.app.graph.state import read_model
from orchestrator.app.schemas.text_layout import ReadabilityReport, SlotReadability, TextLayoutSpec

if TYPE_CHECKING:
    from orchestrator.app.graph.state import MarketingState


def relative_luminance(rgb: tuple[int, int, int]) -> float:
    def channel(value: int) -> float:
        normalized = value / 255
        return normalized / 12.92 if normalized <= 0.03928 else ((normalized + 0.055) / 1.055) ** 2.4

    r, g, b = (channel(component) for component in rgb)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast_ratio(first: tuple[int, int, int] | float, second: tuple[int, int, int] | float) -> float:
    lum1 = first if isinstance(first, float) else relative_luminance(first)
    lum2 = second if isinstance(second, float) else relative_luminance(second)
    lighter = max(lum1, lum2)
    darker = min(lum1, lum2)
    return (lighter + 0.05) / (darker + 0.05)


def average_region_rgb(image: Image.Image, bbox_pixels: tuple[int, int, int, int]) -> tuple[int, int, int]:
    x, y, w, h = bbox_pixels
    region = image.crop((x, y, x + max(w, 1), y + max(h, 1))).convert("RGB")
    pixels = list(region.getdata())
    if not pixels:
        return (255, 255, 255)
    count = len(pixels)
    return (
        sum(pixel[0] for pixel in pixels) // count,
        sum(pixel[1] for pixel in pixels) // count,
        sum(pixel[2] for pixel in pixels) // count,
    )


def classify_wcag_grade(ratio: float, is_large_text: bool) -> str:
    if ratio >= 7.0:
        return "AAA"
    if ratio >= 4.5:
        return "AA"
    if is_large_text and ratio >= 3.0:
        return "AA_LARGE"
    return "FAIL"


def readability_gate_node(state: "MarketingState") -> dict[str, Any]:
    layout = read_model(state, "text_layout_spec", TextLayoutSpec)
    result = state.get("t2i_result") or {}
    background_path = (result.get("image_paths") or [None])[0]
    slots: list[SlotReadability] = []
    remaining_issues: list[str] = []

    if not background_path:
        report = ReadabilityReport(
            overall_pass=False,
            slots=[],
            avg_contrast_ratio=0.0,
            min_contrast_ratio=0.0,
            failed_slot_count=1,
            requires_regeneration=False,
            remaining_issues=["missing background image path"],
        )
        return {"readability_report": report.model_dump(), "status": "final_validating"}

    with Image.open(background_path).convert("RGB") as image:
        for slot in layout.slots:
            background_rgb = average_region_rgb(image, slot.bbox.to_pixels(image.width, image.height))
            text_rgb = hex_to_rgb(slot.text_color)
            bg_lum = relative_luminance(background_rgb)
            text_lum = relative_luminance(text_rgb)
            ratio = contrast_ratio(bg_lum, text_lum)
            estimated_size = slot.effective_font_size_px or int(min(image.width, image.height) * slot.font_metric.base_size_ratio)
            is_large = estimated_size >= max(18, image.width * 0.018)
            grade = classify_wcag_grade(ratio, is_large)
            out_of_safe_area = (
                slot.bbox.x < layout.safe_margin_ratio
                or slot.bbox.y < layout.safe_margin_ratio
                or slot.bbox.x + slot.bbox.w > 1 - layout.safe_margin_ratio
                or slot.bbox.y + slot.bbox.h > 1 - layout.safe_margin_ratio
            )
            overlaps_product = bool(layout.product_zone and bbox_iou(layout.product_zone, slot.bbox) >= 0.10)
            clipped = bool(slot.rendered_text and len(slot.rendered_text) > max(12, slot.max_lines * int(slot.bbox.w * 40)))
            action = "none"
            suggested_overlay = None
            if grade == "FAIL":
                action = "add_overlay"
                suggested_overlay = "solid_panel"
                remaining_issues.append(f"{slot.slot_id} contrast ratio {ratio:.2f} failed")
            slots.append(
                SlotReadability(
                    slot_id=slot.slot_id,
                    role=slot.role,
                    background_luminance=bg_lum,
                    text_luminance=text_lum,
                    contrast_ratio=ratio,
                    wcag_grade=grade,
                    out_of_safe_area=out_of_safe_area,
                    overlaps_product=overlaps_product,
                    clipped=clipped,
                    suggested_text_color="#FFFFFF" if bg_lum < 0.5 else "#111827",
                    suggested_overlay=suggested_overlay,
                    suggested_action=action,
                )
            )

    ratios = [slot.contrast_ratio for slot in slots]
    failed_count = sum(1 for slot in slots if slot.wcag_grade == "FAIL")
    report = ReadabilityReport(
        overall_pass=failed_count == 0,
        slots=[slot.model_dump() for slot in slots],
        avg_contrast_ratio=sum(ratios) / len(ratios) if ratios else 0.0,
        min_contrast_ratio=min(ratios) if ratios else 0.0,
        failed_slot_count=failed_count,
        requires_regeneration=False,
        auto_fixes_applied=[],
        remaining_issues=remaining_issues,
    )
    return {"readability_report": report.model_dump(), "status": "final_validating"}
