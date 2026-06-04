"""Rule-based copy/visual validation helpers for overlay previews."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from PIL import Image, ImageStat


def estimate_text_contrast(image_path: str, text_area: dict[str, Any], text_color: str) -> dict[str, Any]:
    image = Image.open(image_path).convert("RGB")
    bbox = _area_to_bbox(text_area, image.size)
    crop = image.crop(bbox)
    bg_luminance = _relative_luminance(_mean_rgb(crop))
    text_luminance = _relative_luminance(_parse_color(text_color))
    ratio = _contrast_ratio(text_luminance, bg_luminance)
    warnings: list[str] = []
    if ratio < 4.5:
        warnings.append("low_text_contrast")
    bg_tone = "dark" if bg_luminance < 0.35 else "bright" if bg_luminance > 0.72 else "mid"
    recommended_text_tone = "light" if bg_tone == "dark" else "dark"
    plate_required = ratio < 4.5 or bg_tone == "bright"
    shadow_required = ratio < 6.0 or bg_tone in {"bright", "mid"}
    return {
        "contrast_ratio_estimate": round(ratio, 2),
        "background_luminance": round(bg_luminance, 3),
        "text_luminance": round(text_luminance, 3),
        "background_tone": bg_tone,
        "recommended_text_tone": recommended_text_tone,
        "plate_required": plate_required,
        "shadow_required": shadow_required,
        "warnings": warnings,
    }


def validate_text_safe_area(image_path: str, text_area: dict[str, Any]) -> dict[str, Any]:
    image = Image.open(image_path).convert("RGB")
    bbox = _area_to_bbox(text_area, image.size)
    crop = image.crop(bbox).convert("L")
    stat = ImageStat.Stat(crop)
    stddev = float(stat.stddev[0]) if stat.stddev else 0.0
    mean = float(stat.mean[0]) if stat.mean else 0.0
    complexity = round(min(1.0, stddev / 64.0), 3)
    warnings: list[str] = []
    if complexity > 0.45:
        warnings.append("safe_area_complex_background")
    if bbox[2] - bbox[0] < image.width * 0.28 or bbox[3] - bbox[1] < image.height * 0.22:
        warnings.append("safe_area_too_small")
    return {
        "safe_area_background_complexity": complexity,
        "safe_area_luminance_mean": round(mean / 255.0, 3),
        "bbox": bbox,
        "overall_pass": not warnings,
        "warnings": warnings,
    }


def validate_text_clipping(render_result: dict[str, Any]) -> dict[str, Any]:
    if render_result.get("clipping_detected"):
        return {"text_clipping_detected": True, "warnings": ["text_clipping_detected"]}

    canvas = render_result.get("canvas") or {}
    canvas_w = int(canvas.get("width") or render_result.get("canvas_width") or 0)
    canvas_h = int(canvas.get("height") or render_result.get("canvas_height") or 0)
    boxes = render_result.get("text_boxes") or []
    warnings: list[str] = []
    for box in boxes:
        bbox = box.get("bbox") or box
        x1, y1, x2, y2 = [float(value) for value in bbox]
        if canvas_w and canvas_h and (x1 < 0 or y1 < 0 or x2 > canvas_w or y2 > canvas_h):
            warnings.append("text_box_outside_canvas")
            break
    return {"text_clipping_detected": bool(warnings), "warnings": warnings}


def build_copy_visual_validation_report(
    image_path: str,
    text_area: dict[str, Any],
    text_color: str,
    render_result: dict[str, Any] | None = None,
    min_font_size: int | None = None,
) -> dict[str, Any]:
    contrast = estimate_text_contrast(image_path, text_area, text_color)
    safe_area = validate_text_safe_area(image_path, text_area)
    clipping = validate_text_clipping(render_result or {})
    min_font_size_ok = min_font_size is None or min_font_size >= 22
    warnings = sorted(set(contrast["warnings"] + safe_area["warnings"] + clipping["warnings"] + ([] if min_font_size_ok else ["font_size_too_small"])))
    overall_pass = not warnings and contrast["contrast_ratio_estimate"] >= 4.5 and safe_area["overall_pass"]
    return {
        "contrast_ratio_estimate": contrast["contrast_ratio_estimate"],
        "safe_area_background_complexity": safe_area["safe_area_background_complexity"],
        "text_clipping_detected": clipping["text_clipping_detected"],
        "min_font_size_ok": min_font_size_ok,
        "plate_required": contrast["plate_required"],
        "shadow_required": contrast["shadow_required"],
        "overall_pass": overall_pass,
        "warnings": warnings,
        "contrast": contrast,
        "safe_area": safe_area,
        "clipping": clipping,
    }


def _area_to_bbox(area: dict[str, Any], size: tuple[int, int]) -> tuple[int, int, int, int]:
    width, height = size
    x = float(area.get("x", 0))
    y = float(area.get("y", 0))
    w = float(area.get("w", area.get("width", 1)))
    h = float(area.get("h", area.get("height", 1)))
    if max(x, y, w, h) <= 1.0:
        x, y, w, h = x * width, y * height, w * width, h * height
    x1 = max(0, min(width, int(round(x))))
    y1 = max(0, min(height, int(round(y))))
    x2 = max(x1 + 1, min(width, int(round(x + w))))
    y2 = max(y1 + 1, min(height, int(round(y + h))))
    return (x1, y1, x2, y2)


def _mean_rgb(image: Image.Image) -> tuple[float, float, float]:
    stat = ImageStat.Stat(image)
    return tuple(float(value) for value in stat.mean[:3])


def _parse_color(value: str) -> tuple[float, float, float]:
    color = value.strip().lstrip("#")
    if len(color) == 3:
        color = "".join(ch * 2 for ch in color)
    if len(color) != 6:
        return (255.0, 255.0, 255.0)
    return (float(int(color[0:2], 16)), float(int(color[2:4], 16)), float(int(color[4:6], 16)))


def _relative_luminance(rgb: tuple[float, float, float]) -> float:
    values = []
    for channel in rgb:
        value = channel / 255.0
        values.append(value / 12.92 if value <= 0.03928 else ((value + 0.055) / 1.055) ** 2.4)
    return 0.2126 * values[0] + 0.7152 * values[1] + 0.0722 * values[2]


def _contrast_ratio(a: float, b: float) -> float:
    lighter = max(a, b)
    darker = min(a, b)
    return (lighter + 0.05) / (darker + 0.05)
