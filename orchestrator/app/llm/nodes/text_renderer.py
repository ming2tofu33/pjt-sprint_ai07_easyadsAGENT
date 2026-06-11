"""Deterministic PIL text renderer for TLFP."""

from __future__ import annotations

import logging
import math
from pathlib import Path
from typing import TYPE_CHECKING, Any

import colorsys
from PIL import Image, ImageDraw, ImageFont, ImageStat, ImageFilter

logger = logging.getLogger(__name__)

from orchestrator.app.rendering.font_resolver import FONT_CANDIDATES, load_font as load_resolved_font, resolve_font_path
from orchestrator.app.schemas.text_layout import CopyItem, CopySpec, RenderResult, TextLayoutSpec, TextSlot, TextStyleSpec

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
    layout = TextLayoutSpec(**(state.get("text_layout_spec") or {}))
    style = TextStyleSpec(**(state.get("text_style_spec") or {}))
    output_dir = Path("data") / "outputs" / str(state.get("job_id") or "unknown-job")
    output_dir.mkdir(parents=True, exist_ok=True)
    final_path = output_dir / "final_composite.png"

    warnings: list[str] = []
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
        needs_flip = layout.auto_find_empty_space and ((layout_is_right and empty_half == "left") or (not layout_is_right and empty_half == "right"))
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
            
            # Smart Rendering Pipeline: Dynamic Color and Overlay
            crop = image.crop((x, y, x + w, y + h))
            stat = ImageStat.Stat(crop)
            # Complexity check
            stddev = sum(stat.stddev) / len(stat.stddev) if stat.stddev else 0
            complexity = min(1.0, stddev / 64.0)
            if complexity > 0.45 and slot.overlay_treatment not in {"solid_panel", "gradient_panel", "blur_backdrop"}:
                slot.overlay_treatment = "solid_panel"
                if not slot.overlay_color:
                    slot.overlay_color = style.typography.primary_color
            
            # Color Selection Strategy
            bg_rgb = tuple(float(v) for v in stat.mean[:3])
            bg_lum = _relative_luminance(bg_rgb)
            
            target_contrast = _get_contrast_target(slot.role)
            
            contrast_margin = 0.0
            
            if slot.role == "cta" and slot.overlay_treatment == "solid_panel":
                # Exception Rule: CTA 버튼 가독성 최우선
                w_rgb = hex_to_rgb("#FFFFFF")
                b_rgb = hex_to_rgb("#111827")
                w_ratio = _contrast_ratio(_relative_luminance(w_rgb), bg_lum)
                b_ratio = _contrast_ratio(_relative_luminance(b_rgb), bg_lum)
                
                if w_ratio >= target_contrast:
                    slot.text_color = "#FFFFFF"
                elif b_ratio >= target_contrast:
                    slot.text_color = "#111827"
                else:
                    slot.text_color = "#FFFFFF" if w_ratio > b_ratio else "#111827"
                
                c_rgb = tuple(float(v) for v in hex_to_rgb(slot.text_color))
                c_ratio = _contrast_ratio(_relative_luminance(c_rgb), bg_lum)
                contrast_margin = c_ratio - target_contrast
                
                logger.info(f"CTA Color Rule Applied | BG: {bg_lum:.2f} | Selected: {slot.text_color} (Margin: {contrast_margin:.1f})")
            else:
                primary = style.typography.primary_color
                accent = style.typography.accent_color
                tone_color = _generate_tone_on_tone_candidate(bg_rgb, bg_lum, target_contrast)
                
                candidates = {
                    "Brand Primary": primary,
                    "Brand Accent": accent,
                }
                if tone_color:
                    candidates["Tone-on-Tone"] = tone_color
                    
                best_color = None
                best_score = -1.0
                
                logger.info(f"--- Scoring Engine Started: {slot.role} ---")
                logger.info(f"Background RGB: {bg_rgb}, Lum: {bg_lum:.2f}, Target: {target_contrast}")
                
                primary_rgb = hex_to_rgb(primary)
                accent_rgb = hex_to_rgb(accent)
                
                for cand_name, cand_hex in candidates.items():
                    c_rgb = tuple(float(v) for v in hex_to_rgb(cand_hex))
                    c_lum = _relative_luminance(c_rgb)
                    c_ratio = _contrast_ratio(c_lum, bg_lum)
                    
                    if c_ratio < target_contrast:
                        logger.info(f"[{cand_name}] {cand_hex} - FAILED Contrast ({c_ratio:.2f} < {target_contrast})")
                        continue
                        
                    contrast_score = _calculate_contrast_score(c_ratio)
                    harmony_score = _calculate_harmony_score(c_rgb, bg_rgb)
                    brand_score = _calculate_brand_score(c_rgb, primary_rgb, accent_rgb)
                    
                    final_score = (contrast_score * 0.3) + (harmony_score * 0.5) + (brand_score * 0.2)
                    
                    logger.info(f"[{cand_name}] {cand_hex} - Pass! "
                                 f"Contrast:{contrast_score:.1f}({c_ratio:.1f}) "
                                 f"Harmony:{harmony_score:.1f} Brand:{brand_score:.1f} "
                                 f"-> Final:{final_score:.1f}")
                                 
                    if final_score > best_score:
                        best_score = final_score
                        best_color = cand_hex
                        
                if best_color:
                    slot.text_color = best_color
                    c_rgb = tuple(float(v) for v in hex_to_rgb(best_color))
                    c_ratio = _contrast_ratio(_relative_luminance(c_rgb), bg_lum)
                    contrast_margin = c_ratio - target_contrast
                    logger.info(f"Selected: {best_color} with score {best_score:.1f} (Margin: {contrast_margin:.1f})")
                else:
                    # Fallback
                    w_ratio = _contrast_ratio(1.0, bg_lum)
                    b_ratio = _contrast_ratio(0.0, bg_lum)
                    slot.text_color = style.typography.text_color_on_dark if w_ratio > b_ratio else style.typography.text_color_on_light
                    contrast_margin = max(w_ratio, b_ratio) - target_contrast
                    logger.warning(f"All candidates failed! Fallback to {slot.text_color} (Margin: {contrast_margin:.1f})")
            
            # Dynamic Font Scaling Loop
            base_font_size = estimate_font_size(slot, image.width, image.height)
            min_font_size = max(18, int(min(image.width, image.height) * slot.font_metric.min_size_ratio))
            
            best_font = None
            best_lines = []
            font_warning = None
            
            font_size = base_font_size
            while font_size >= min_font_size:
                font, f_warn = load_font(slot, font_size)
                lines = wrap_text_by_pixel(copy_item.text, font, max_width=w, max_lines=slot.max_lines)
                
                is_truncated = len(lines) >= slot.max_lines and len(copy_item.text) > len(" ".join(lines))
                line_height = int(getattr(font, "size", 18) * slot.font_metric.line_height_em)
                actual_h = line_height * len(lines)
                
                if not is_truncated and actual_h <= h:
                    best_font = font
                    best_lines = lines
                    font_warning = f_warn
                    break
                    
                font_size -= 2
                
            if not best_font:
                # Fallback to minimum size if it couldn't fit
                font_size = max(18, min_font_size)
                best_font, font_warning = load_font(slot, font_size)
                best_lines = wrap_text_by_pixel(copy_item.text, best_font, max_width=w, max_lines=slot.max_lines)
                
            font = best_font
            lines = best_lines
            if font_warning:
                warnings.append(font_warning)
            if len(lines) >= slot.max_lines and len(copy_item.text) > len(" ".join(lines)):
                warnings.append(f"slot {slot.slot_id} clipping risk: text truncated to {slot.max_lines} lines")
            
            line_height = int(getattr(font, "size", 18) * slot.font_metric.line_height_em)
            actual_h = line_height * len(lines)
            actual_y = y + max(0, (h - actual_h) // 2)
            
            draw_overlay(draw, slot, x, actual_y, w, actual_h, style)
            draw_wrapped_text(draw, lines, slot, font, x, y, w, h, complexity, contrast_margin)
            rendered_count += 1
        image.save(final_path)

    render_result = RenderResult(
        background_image_path=str(background_path),
        final_image_path=str(final_path),
        rendered_slot_count=rendered_count,
        skipped_slot_count=skipped_count,
        warnings=warnings,
        metadata={"source_node": "text_renderer", "has_text_overlay": rendered_count > 0},
    )
    artifacts = list(state.get("artifact_refs") or [])
    artifacts.append(
        {
            "type": "final_image",
            "path": str(final_path),
            "metadata": {"source": "text_renderer", "has_text_overlay": rendered_count > 0},
        }
    )
    return {
        "final_image_path": str(final_path),
        "render_result": render_result.model_dump(),
        "text_overlay_pending": False,
        "artifact_refs": artifacts,
        "status": "overlaying_text",
    }


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


def load_font(slot: TextSlot, size: int) -> tuple[ImageFont.FreeTypeFont | ImageFont.ImageFont, str | None]:
    weight = "bold" if slot.font_metric.weight >= 700 else None
    preferred = slot.font_metric.font_family
    font = load_resolved_font(
    size=size,
    weight=weight,
    preferred=preferred,)
    if preferred and font and hasattr(font, "path"):
        return font, None
    if not resolve_font_path(preferred):
        return font, f"slot {slot.slot_id} used default PIL font fallback"
    return font, None


def wrap_text_by_pixel(text: str, font: ImageFont.ImageFont, max_width: int, max_lines: int) -> list[str]:
    words = text.split()
    if not words:
        words = [text]
    lines: list[str] = []
    current = ""
    for word in words:
        candidate = f"{current} {word}".strip()
        try:
            width = font.getbbox(candidate)[2]
        except AttributeError:
            width = font.getsize(candidate)[0] if hasattr(font, "getsize") else len(candidate) * 15
            
        if width <= max_width:
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
    if len(lines) == max_lines and len(" ".join(words)) > len(" ".join(lines)):
        lines[-1] = lines[-1].rstrip(". ") + "..."
    return lines or [text]


def draw_overlay(draw: ImageDraw.ImageDraw, slot: TextSlot, x: int, y: int, w: int, h: int, style: TextStyleSpec) -> None:
    treatment = slot.overlay_treatment
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
    radius = max(10, pad * (2 if slot.role == "cta" else 1))
    draw.rounded_rectangle((x - pad, y - pad, x + w + pad, y + h + pad), radius=radius, fill=(r, g, b, alpha))


def draw_wrapped_text(draw: ImageDraw.ImageDraw, lines: list[str], slot: TextSlot, font: ImageFont.ImageFont, x: int, y: int, w: int, h: int, complexity: float = 0.0, contrast_margin: float = 99.0) -> None:
    fill = hex_to_rgb(slot.text_color) + (255,)
    line_height = int(getattr(font, "size", 18) * slot.font_metric.line_height_em)
    total_h = line_height * len(lines)
    cursor_y = y + max(0, (h - total_h) // 2)
    
    # Pre-calculate positions
    positions = []
    for line in lines:
        try:
            bbox = font.getbbox(line)
            text_w = bbox[2] - bbox[0]
        except AttributeError:
            text_w = font.getsize(line)[0] if hasattr(font, "getsize") else len(line) * 15
            
        if slot.alignment == "left":
            cursor_x = x
        elif slot.alignment == "right":
            cursor_x = x + max(0, w - text_w)
        else:
            cursor_x = x + max(0, (w - text_w) // 2)
        positions.append((line, cursor_x, cursor_y))
        cursor_y += line_height

    # Draw shadow layer first if needed
    if slot.overlay_treatment in {"drop_shadow", "stroke"}:
        draw_shadow = False
        shadow_opacity = 0
        
        if slot.role == "cta":
            draw_shadow = False
        elif slot.role == "headline":
            if complexity > 0.45 and contrast_margin < 1.0:
                draw_shadow = True
                shadow_opacity = 70
        else:
            if complexity > 0.25 or contrast_margin < 1.0:
                draw_shadow = True
                shadow_opacity = 40
                
        if draw_shadow:
            shadow_image = Image.new("RGBA", draw._image.size, (0, 0, 0, 0))
            shadow_draw = ImageDraw.Draw(shadow_image)
            font_size = getattr(font, "size", 18)
            offset_val = min(max(1, int(font_size * 0.035)), 4)
            
            for line, cx, cy in positions:
                shadow_draw.text((cx + offset_val, cy + offset_val), line, font=font, fill=(0, 0, 0, shadow_opacity))
            
            # Apply Gaussian Blur
            blur_radius = min(max(2, int(font_size * 0.1)), 10)
            shadow_image = shadow_image.filter(ImageFilter.GaussianBlur(radius=blur_radius))
            
            # Paste shadow onto original
            draw._image.paste(shadow_image, (0, 0), shadow_image)

    # Draw actual text
    for line, cx, cy in positions:
        draw.text((cx, cy), line, font=font, fill=fill)


def hex_to_rgb(value: str) -> tuple[int, int, int]:
    cleaned = value.strip().lstrip("#")
    if len(cleaned) != 6:
        return (255, 255, 255)
    return tuple(int(cleaned[index : index + 2], 16) for index in (0, 2, 4))


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


def _get_contrast_target(role: str) -> float:
    if role == "headline":
        return 3.0
    return 4.5


def _calculate_contrast_score(ratio: float) -> float:
    return min(100.0, (ratio / 21.0) * 100.0)


def _calculate_harmony_score(cand_rgb: tuple[float, float, float], bg_rgb: tuple[float, float, float]) -> float:
    c_h, c_l, c_s = colorsys.rgb_to_hls(*[v/255.0 for v in cand_rgb])
    b_h, b_l, b_s = colorsys.rgb_to_hls(*[v/255.0 for v in bg_rgb])
    
    hue_dist = min(abs(c_h - b_h), 1.0 - abs(c_h - b_h))
    hue_score = max(0.0, (0.5 - hue_dist) * 200.0)
    
    sat_score = 100.0
    if c_s > 0.7:
        sat_score -= (c_s - 0.7) * 100.0
        
    return (hue_score * 0.7) + (sat_score * 0.3)


def _calculate_brand_score(cand_rgb: tuple[float, float, float], primary_rgb: tuple[float, float, float], accent_rgb: tuple[float, float, float]) -> float:
    dist_p = math.sqrt(sum((c - p)**2 for c, p in zip(cand_rgb, primary_rgb)))
    dist_a = math.sqrt(sum((c - a)**2 for c, a in zip(cand_rgb, accent_rgb)))
    best_dist = min(dist_p, dist_a)
    return max(0.0, 100.0 * (1.0 - best_dist / 441.67))


def _generate_tone_on_tone_candidate(bg_rgb: tuple[float, float, float], bg_lum: float, target_contrast: float) -> str | None:
    r, g, b = [c / 255.0 for c in bg_rgb]
    h, l, s = colorsys.rgb_to_hls(r, g, b)
    
    # Saturation 20% 감소
    s = max(0.0, s * 0.8)
    
    # Lightness Adjustment Constraints
    step = 0.05
    w_ratio = _contrast_ratio(1.0, bg_lum)
    b_ratio = _contrast_ratio(0.0, bg_lum)
    direction = 1 if w_ratio > b_ratio else -1
    
    current_l = l
    iterations = 0
    max_iterations = 20
    
    while iterations < max_iterations:
        current_l += direction * step
        
        # Stop when Lightness reaches 0.0 or 1.0
        if current_l <= 0.0:
            current_l = 0.0
            r_out, g_out, b_out = colorsys.hls_to_rgb(h, current_l, s)
            return f"#{int(r_out*255):02x}{int(g_out*255):02x}{int(b_out*255):02x}"
        if current_l >= 1.0:
            current_l = 1.0
            r_out, g_out, b_out = colorsys.hls_to_rgb(h, current_l, s)
            return f"#{int(r_out*255):02x}{int(g_out*255):02x}{int(b_out*255):02x}"
            
        r_out, g_out, b_out = colorsys.hls_to_rgb(h, current_l, s)
        rgb_tuple = (r_out * 255.0, g_out * 255.0, b_out * 255.0)
        text_lum = _relative_luminance(rgb_tuple)
        ratio = _contrast_ratio(text_lum, bg_lum)
        
        # Stop immediately when Contrast Target is satisfied
        if ratio >= target_contrast:
            return f"#{int(r_out*255):02x}{int(g_out*255):02x}{int(b_out*255):02x}"
            
        iterations += 1
        
    return None
