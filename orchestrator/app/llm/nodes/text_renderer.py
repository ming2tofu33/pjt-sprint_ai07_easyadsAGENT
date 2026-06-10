"""Deterministic PIL text renderer for TLFP."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any

from PIL import Image, ImageDraw, ImageFont, ImageStat

from orchestrator.app.rendering.font_resolver import FONT_CANDIDATES, ResolvedFont, load_font as load_resolved_font, resolve_font, resolve_font_path
from orchestrator.app.rendering.text_metrics import draw_text_with_tracking, fit_text_block_to_bbox, measure_text_with_tracking
from orchestrator.app.rendering.typography_color import choose_text_color
from orchestrator.app.schemas.text_layout import CopyItem, CopySpec, RenderResult, TextLayoutSpec, TextSlot, TextStyleSpec, TypographyRenderTrace

if TYPE_CHECKING:
    from orchestrator.app.graph.state import MarketingState


SYSTEM_FONT_CANDIDATES = FONT_CANDIDATES


def text_renderer_node(state: "MarketingState") -> dict[str, Any]:
    result = state.get("t2i_result") or {}
    image_paths = result.get("image_paths") or []
    background_path = image_paths[0] if image_paths else None
    if not background_path:
        render_result = RenderResult(
            background_image_path="",
            final_image_path="",
            rendered_slot_count=0,
            skipped_slot_count=0,
            warnings=["missing background image path"],
            metadata={"source_node": "text_renderer"},
        )
        return {"render_result": render_result.model_dump(), "status": "failed", "error_message": "missing background image path"}

    copy_spec = CopySpec(**(state.get("copy_spec") or {}))
    layout_data, style_data = _apply_regeneration_layout_patch(state.get("text_layout_spec") or {}, state.get("text_style_spec") or {}, state.get("regeneration_patch") or {})
    layout = TextLayoutSpec(**layout_data)
    style = TextStyleSpec(**style_data)
    output_dir = Path("data") / "outputs" / str(state.get("job_id") or "unknown-job")
    output_dir.mkdir(parents=True, exist_ok=True)
    final_path = output_dir / "final_composite.png"
    preview_path = output_dir / "failed_composite_preview.png"

    warnings: list[str] = []
    overflow_errors: list[str] = []
    render_traces: list[dict[str, Any]] = []
    rendered_count = 0
    skipped_count = 0
    with Image.open(background_path).convert("RGB") as image:
        empty_half = find_empty_half(image)
        
        # 슬롯들의 평균 중심 x 좌표를 통해 텍스트 레이아웃의 방향 파악
        avg_x = 0.5
        if layout.slots:
            avg_x = sum(slot.bbox.x + slot.bbox.w / 2 for slot in layout.slots) / len(layout.slots)
            
        layout_is_right = avg_x > 0.5
        
        # 텍스트가 가야할 빈 공간(empty_half)과 현재 기획된 텍스트 위치(layout_is_right)가 엇갈릴 경우
        image_aware_layout_locked = bool(state.get("image_layout_analysis")) and bool((state.get("layout_refinement_result") or {}).get("selected_candidate_id") if isinstance(state.get("layout_refinement_result"), dict) else False)
        needs_flip = (not image_aware_layout_locked) and layout.auto_find_empty_space and ((layout_is_right and empty_half == "left") or (not layout_is_right and empty_half == "right"))
        if needs_flip:
            warnings.append(f"Auto-flipped layout horizontally to match image negative space ({empty_half})")

        draw = ImageDraw.Draw(image, "RGBA")
        for slot in layout.slots:
            copy_item = find_copy_item(copy_spec, slot)
            if not copy_item:
                skipped_count += 1
                warnings.append(f"slot {slot.slot_id} skipped: no matching copy item")
                continue
                
            if needs_flip:
                # 가로(x) 좌표 반전 및 좌/우 정렬 반전
                slot.bbox.x = 1.0 - slot.bbox.x - slot.bbox.w
                if slot.alignment == "left":
                    slot.alignment = "right"
                elif slot.alignment == "right":
                    slot.alignment = "left"
                    
            if slot.alignment == "auto":
                slot.alignment = "right" if slot.bbox.x > 0.5 else "left"
                
            x, y, w, h = slot.bbox.to_pixels(image.width, image.height)
            max_size = max(1, int(min(image.width, image.height) * slot.font_metric.max_size_ratio))
            min_size = max(1, int(min(image.width, image.height) * slot.font_metric.min_size_ratio))
            estimated_size = estimate_font_size(slot, image.width, image.height)
            fit = fit_text_block_to_bbox(
                copy_item.text,
                font_factory=lambda size, current_slot=slot: load_font(current_slot, size)[0],
                bbox_width=max(1, w),
                bbox_height=max(1, h),
                max_lines=slot.max_lines,
                max_size=max(max_size, estimated_size),
                min_size=min(min_size, estimated_size),
                line_height_ratio=slot.font_metric.line_height_em,
                letter_spacing_em=slot.font_metric.letter_spacing_em,
            )
            font_size = int(fit["font_size"])
            font, resolved_font, font_warning = load_font(slot, font_size)
            if font_warning:
                warnings.append(font_warning)
            if resolved_font.fallback_used:
                overflow_errors.append(f"slot {slot.slot_id} font fallback used: {resolved_font.source}")
                continue
            lines = list(fit["lines"])
            if not fit["fits"]:
                overflow_errors.append(f"slot {slot.slot_id} overflow: text does not fit within {slot.max_lines} lines")
                continue
            
            line_height = int(getattr(font, "size", 18) * slot.font_metric.line_height_em)
            actual_h = line_height * len(lines)
            actual_y = y + max(0, (h - actual_h) // 2)
            color_result = choose_text_color(image, (x, y, w, h), role=slot.role, preferred=slot.text_color)
            slot.text_color = color_result["text_color"]
            draw_overlay(draw, slot, x, actual_y, w, actual_h, style, lines=lines, font=font)
            rendered_bbox = draw_wrapped_text(draw, lines, slot, font, x, y, w, h)
            slot.rendered_lines = lines
            slot.effective_font_size_px = font_size
            slot.effective_weight = resolved_font.resolved_weight
            trace = TypographyRenderTrace(
                role=slot.role,
                font_id=resolved_font.font_id,
                family_id=resolved_font.family_id,
                resolved_weight=resolved_font.resolved_weight,
                source=resolved_font.source,
                effective_font_size_px=font_size,
                rendered_lines=lines,
                rendered_bbox_px=rendered_bbox,
                letter_spacing_px=round(float(fit.get("tracking_px") or font_size * slot.font_metric.letter_spacing_em), 2),
                line_height_px=line_height,
                text_color=slot.text_color,
                contrast_ratio_min=float(color_result["contrast_ratio"]),
                contrast_ratio_average=float(color_result["contrast_ratio"]),
                overlay_treatment=slot.overlay_treatment,
                overlay_bbox_px=None,
                fallback_used=resolved_font.fallback_used,
                warnings=[],
            )
            render_traces.append(trace.model_dump())
            rendered_count += 1
        image.save(preview_path if overflow_errors else final_path)

    render_result = RenderResult(
        background_image_path=str(background_path),
            final_image_path=str(final_path if not overflow_errors else preview_path),
        rendered_slot_count=rendered_count,
        skipped_slot_count=skipped_count,
        warnings=warnings + overflow_errors,
        metadata={"source_node": "text_renderer", "has_text_overlay": rendered_count > 0, "overflow_detected": bool(overflow_errors), "typography_render_traces": render_traces},
    )
    artifacts = list(state.get("artifact_refs") or [])
    if overflow_errors:
        artifacts.append(
            {
                "type": "validation_preview",
                "path": str(preview_path),
                "metadata": {"source": "text_renderer", "has_text_overlay": rendered_count > 0, "overflow_detected": True},
            }
        )
    else:
        artifacts.append(
            {
                "type": "final_image",
                "path": str(final_path),
                "metadata": {"source": "text_renderer", "has_text_overlay": rendered_count > 0},
            }
        )
    return {
        "final_image_path": None if overflow_errors else str(final_path),
        "render_result": render_result.model_dump(),
        "text_overlay_pending": False,
        "artifact_refs": artifacts,
        "status": "failed" if overflow_errors else "overlaying_text",
        "error_message": "; ".join(overflow_errors) if overflow_errors else None,
    }


def _apply_regeneration_layout_patch(layout_value: object, style_value: object, patch_value: object) -> tuple[dict[str, Any], dict[str, Any]]:
    layout = dict(layout_value) if isinstance(layout_value, dict) else {}
    style = dict(style_value) if isinstance(style_value, dict) else {}
    patches = patch_value.get("patches") if isinstance(patch_value, dict) else {}
    for patch in (patches or {}).values():
        if not isinstance(patch, dict):
            continue
        if patch.get("target") == "layout":
            if patch.get("safeAreaScale"):
                layout["safe_margin_ratio"] = min(0.5, float(layout.get("safe_margin_ratio") or 0.06) * float(patch["safeAreaScale"]))
            slots = []
            for raw_slot in layout.get("slots") or []:
                slot = dict(raw_slot) if isinstance(raw_slot, dict) else raw_slot
                if isinstance(slot, dict):
                    if patch.get("increasePadding"):
                        slot["inner_padding_ratio"] = min(0.5, float(slot.get("inner_padding_ratio") or 0.04) + 0.02)
                    if patch.get("reduceFontScale"):
                        metric = dict(slot.get("font_metric") or {})
                        if metric.get("base_size_ratio") is not None:
                            metric["base_size_ratio"] = max(0.01, float(metric["base_size_ratio"]) * 0.9)
                        slot["font_metric"] = metric
                    if patch.get("rewrapText"):
                        slot["max_lines"] = max(int(slot.get("max_lines") or 1) + 1, 2)
                slots.append(slot)
            if slots:
                layout["slots"] = slots
        if patch.get("target") == "textStyle":
            typography = dict(style.get("typography") or {})
            if patch.get("increaseContrast"):
                typography["use_text_plate"] = True
            if patch.get("enableShadowOrOverlay"):
                typography["default_overlay"] = typography.get("default_overlay") or "drop_shadow"
            if typography:
                style["typography"] = typography
    return layout, style


def find_empty_half(image: Image.Image) -> str:
    """
    Returns 'left' or 'right' depending on which half of the image has lower variance/details.
    Lower standard deviation implies more flat negative space.
    """
    gray = image.convert("L")
    w, h = gray.size
    left_half = gray.crop((0, 0, w // 2, h))
    right_half = gray.crop((w // 2, 0, w, h))
    
    left_stddev = sum(ImageStat.Stat(left_half).stddev)
    right_stddev = sum(ImageStat.Stat(right_half).stddev)
    
    return "left" if left_stddev < right_stddev else "right"


def find_copy_item(copy_spec: CopySpec, slot: TextSlot) -> CopyItem | None:
    renderable = copy_spec.get_renderable()
    if slot.bound_copy_id:
        suffix = slot.bound_copy_id.split(":")[-1]
        for item in renderable:
            if item.role == suffix:
                return item
    return next((item for item in renderable if item.role == slot.role), None)


def estimate_font_size(slot: TextSlot, canvas_w: int, canvas_h: int) -> int:
    if slot.effective_font_size_px:
        return slot.effective_font_size_px
    base = int(min(canvas_w, canvas_h) * slot.font_metric.base_size_ratio)
    role_multiplier = {
        "headline": 1.12,
        "subheadline": 0.86,
        "body": 0.74,
        "promotion": 0.82,
        "badge": 0.78,
        "cta": 0.72,
        "store_info": 0.66,
        "disclaimer": 0.55,
    }.get(slot.role, 1.0)
    base = int(base * role_multiplier)
    minimum = int(min(canvas_w, canvas_h) * slot.font_metric.min_size_ratio)
    maximum = int(min(canvas_w, canvas_h) * slot.font_metric.max_size_ratio)
    return max(18, min(maximum, max(minimum, base)))


def load_font(slot: TextSlot, size: int) -> tuple[ImageFont.FreeTypeFont | ImageFont.ImageFont, ResolvedFont, str | None]:
    preferred = slot.font_metric.font_family
    try:
        font, resolved = resolve_font(family_id=preferred, weight=slot.font_metric.weight, size_px=size)
        warning = f"slot {slot.slot_id} used {resolved.source} font fallback" if resolved.fallback_used else None
        return font, resolved, warning
    except Exception:
        weight = "bold" if slot.font_metric.weight >= 700 else None
        font = load_resolved_font(size=size, weight=weight, preferred=preferred)
        resolved = ResolvedFont(font_id="unknown", family_id=str(preferred or "unknown"), requested_weight=slot.font_metric.weight, resolved_weight=slot.font_metric.weight, source="pil_default", fallback_used=True)
        return font, resolved, f"slot {slot.slot_id} used default PIL font fallback"


def wrap_text(text: str, max_chars: int, max_lines: int) -> list[str]:
    words = text.split()
    if not words:
        words = [text]
    lines: list[str] = []
    current = ""
    for word in words:
        candidate = f"{current} {word}".strip()
        if len(candidate) <= max_chars:
            current = candidate
            continue
        if current:
            lines.append(current)
        current = word
        if len(lines) >= max_lines:
            break
    if current and len(lines) < max_lines:
        lines.append(current)
    if len(lines) > max_lines:
        lines = lines[:max_lines]
    return lines or [text[:max_chars]]


def draw_overlay(
    draw: ImageDraw.ImageDraw,
    slot: TextSlot,
    x: int,
    y: int,
    w: int,
    h: int,
    style: TextStyleSpec,
    *,
    lines: list[str] | None = None,
    font: ImageFont.ImageFont | None = None,
) -> None:
    treatment = slot.overlay_treatment
    cta_style = ((style.role_styles or {}).get("cta") or {}).get("style") if slot.role == "cta" else None
    if slot.role == "cta" and cta_style in {"none", "text_link"}:
        return
    if slot.role == "cta" and treatment in {"drop_shadow", "stroke"} and slot.overlay_opacity > 0:
        treatment = "solid_panel"
    if slot.role in {"promotion", "badge"} and treatment == "plain":
        treatment = "sticker_badge"
    if style.typography.use_text_plate and treatment == "plain":
        treatment = "solid_panel"
    if treatment not in {"solid_panel", "gradient_panel", "sticker_badge", "blur_backdrop"}:
        return
    color = slot.overlay_color or (style.typography.accent_color if slot.role == "cta" else style.typography.primary_color)
    r, g, b = hex_to_rgb(color)
    alpha = int(255 * max(slot.overlay_opacity, 0.72))
    pad = max(10, int(min(w, h) * max(slot.inner_padding_ratio, 0.08 if slot.role == "cta" else 0.05)))
    box_x, box_y, box_w, box_h = x, y, w, h
    if slot.role == "cta" and cta_style in {"small_label", "pill_button"} and lines and font:
        text_w = max((draw.textbbox((0, 0), line, font=font)[2] - draw.textbbox((0, 0), line, font=font)[0]) for line in lines)
        box_w = min(w, text_w)
        if slot.alignment == "center":
            box_x = x + max(0, (w - box_w) // 2)
        elif slot.alignment == "right":
            box_x = x + max(0, w - box_w)
        pad = max(8, int(getattr(font, "size", 18) * (0.22 if cta_style == "small_label" else 0.45)))
    radius = max(6, pad * (3 if slot.role == "cta" and cta_style == "pill_button" else 1))
    draw.rounded_rectangle((box_x - pad, box_y - pad, box_x + box_w + pad, box_y + box_h + pad), radius=radius, fill=(r, g, b, alpha))


def draw_wrapped_text(draw: ImageDraw.ImageDraw, lines: list[str], slot: TextSlot, font: ImageFont.ImageFont, x: int, y: int, w: int, h: int) -> tuple[int, int, int, int]:
    fill = hex_to_rgb(slot.text_color) + (255,)
    line_height = int(getattr(font, "size", 18) * slot.font_metric.line_height_em)
    total_h = line_height * len(lines)
    cursor_y = y + max(0, (h - total_h) // 2)
    tracking_px = max(-2.0, min(8.0, getattr(font, "size", 18) * slot.font_metric.letter_spacing_em))
    min_x = x + w
    min_y = cursor_y
    max_x = x
    max_y = cursor_y
    for line in lines:
        text_w = int(measure_text_with_tracking(draw, line, font=font, tracking_px=tracking_px))
        if slot.alignment == "left":
            cursor_x = x
        elif slot.alignment == "right":
            cursor_x = x + max(0, w - text_w)
        else:
            cursor_x = x + max(0, (w - text_w) // 2)
        if slot.overlay_treatment in {"drop_shadow", "stroke"}:
            draw_text_with_tracking(draw, (cursor_x + 2, cursor_y + 2), line, font=font, fill=(0, 0, 0, 150), tracking_px=tracking_px)
        draw_text_with_tracking(draw, (cursor_x, cursor_y), line, font=font, fill=fill, tracking_px=tracking_px)
        min_x = min(min_x, cursor_x)
        max_x = max(max_x, cursor_x + text_w)
        max_y = max(max_y, cursor_y + line_height)
        cursor_y += line_height
    return (int(min_x), int(min_y), int(max_x), int(max_y))


def hex_to_rgb(value: str) -> tuple[int, int, int]:
    cleaned = value.strip().lstrip("#")
    if len(cleaned) != 6:
        return (255, 255, 255)
    return tuple(int(cleaned[index : index + 2], 16) for index in (0, 2, 4))
