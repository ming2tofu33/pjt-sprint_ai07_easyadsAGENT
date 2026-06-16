"""Component-based poster renderer for Phase 1.6: Quality Gate & Text Fitting."""

import logging
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFont, ImageStat, ImageFilter

from orchestrator.app.schemas.poster_layout import PosterComponent, PosterLayoutSpec
from orchestrator.app.schemas.text_layout import RenderResult
from orchestrator.app.rendering.font_resolver import load_font

from orchestrator.app.rendering.palette_extractor import extract_palette
from orchestrator.app.rendering.contrast_analyzer import analyze_bbox_background, select_best_text_color


logger = logging.getLogger(__name__)


def wrap_text(text: str, font: ImageFont.FreeTypeFont, max_width: int) -> list[str]:
    words = text.split()
    if not words:
        return []
    lines = []
    current_line = []
    
    for word in words:
        current_line.append(word)
        line_str = " ".join(current_line)
        try:
            w = font.getbbox(line_str)[2]
        except AttributeError:
            w = font.getsize(line_str)[0] if hasattr(font, "getsize") else len(line_str) * font.size
            
        if w > max_width and len(current_line) > 1:
            current_line.pop()
            lines.append(" ".join(current_line))
            current_line = [word]
            
    if current_line:
        lines.append(" ".join(current_line))
    return lines


def fit_text(text: str, font_weight: str, base_size: int, max_w: int, max_h: int, font_family_id: str | None = None) -> dict:
    min_size = max(10, int(base_size * 0.4))
    current_size = base_size
    font_scaled = False
    truncated = False
    clipped_by_bbox = False
    
    lines = []
    font = None
    line_height = 0
    final_w = 0
    final_h = 0
    
    while current_size >= min_size:
        font = load_font(size=current_size, weight=font_weight, preferred=font_family_id) or ImageFont.load_default()
        line_height = int(current_size * 1.2)
        lines = wrap_text(text, font, max_w)
        final_h = line_height * len(lines)
        
        if final_h <= max_h:
            break
        
        current_size -= 2
        font_scaled = True
        
    # If still overflowing at min size, truncate
    if final_h > max_h:
        max_lines = max(1, max_h // line_height)
        lines = lines[:max_lines]
        if lines:
            # Truncate the last line
            last_line = lines[-1]
            while len(last_line) > 0:
                test_str = last_line + "..."
                try:
                    tw = font.getbbox(test_str)[2]
                except AttributeError:
                    tw = font.getsize(test_str)[0] if hasattr(font, "getsize") else len(test_str) * current_size
                if tw <= max_w:
                    lines[-1] = test_str
                    break
                last_line = last_line[:-1]
            if len(last_line) == 0:
                lines[-1] = "..."
        truncated = True
        final_h = line_height * len(lines)
        
    # Calculate final width
    final_w = 0
    for line in lines:
        try:
            w = font.getbbox(line)[2]
        except AttributeError:
            w = font.getsize(line)[0] if hasattr(font, "getsize") else len(line) * current_size
        final_w = max(final_w, w)
        
    # Check physical clipping (if it still exceeds boundaries after all efforts)
    if final_w > max_w or final_h > max_h:
        clipped_by_bbox = True
        
    final_overflow_detected = clipped_by_bbox
    
    return {
        "lines": lines,
        "font": font,
        "font_size": current_size,
        "font_scaled": font_scaled,
        "truncated": truncated,
        "final_w": final_w,
        "final_h": final_h,
        "clipped_by_bbox": clipped_by_bbox,
        "final_overflow_detected": final_overflow_detected
    }


def _draw_text_block_with_shadow(component: PosterComponent, image_width: int, image_height: int, font_weight="bold", base_size_ratio=0.08, **kwargs) -> tuple[Image.Image, dict]:
    x, y, w, h = component.bbox.to_pixels(image_width, image_height)
    
    content = component.content
    text = " ".join(content.get("lines", [])) if isinstance(content, dict) else str(content)
    style = component.style
    
    base_size = style.get("font_size", int(min(image_width, image_height) * base_size_ratio))
    color = style.get("text_color", "#FFFFFF")
    
    add_shadow = style.get("add_soft_shadow", False)
    shadow_color = style.get("shadow_color", "#000000")
    shadow_opacity = 0.30
    
    # --- Dynamic Contrast Logic ---
    render_opts = kwargs.get("render_options", {})
    palette = kwargs.get("extracted_palette", {})
    bg_img = kwargs.get("background_image")
    color_decision = None
    soft_surface_applied = False
    
    if render_opts.get("enable_local_contrast_text") and bg_img:
        bg_analysis = analyze_bbox_background(bg_img, (x, y, x + w, y + h))
        candidates = []
        if palette:
            candidates.extend([
                palette.get("dark_text_candidate", "#2E241C"),
                palette.get("light_text_candidate", "#FFF8F0"),
                "#FFFFFF",
                "#000000"
            ])
        else:
            candidates = ["#FFFFFF", "#000000", "#333333", "#F0F0F0"]
            
        best_c, ratio, needs_surface = select_best_text_color(candidates, bg_analysis["luminance"])
        color = best_c
        
        shadow_reason = "Not applied (contrast sufficient)"
        if ratio < 4.5:
            add_shadow = True
            shadow_reason = "Contrast ratio < 4.5, applied shadow for legibility"
        else:
            add_shadow = False
            
        if ratio < 3.0:
            soft_surface_applied = True
            shadow_reason = "Contrast ratio < 3.0, applied soft surface"
            
        color_decision = {
            "color_source": "image_adaptive" if palette else "fallback",
            "shadow_reason": shadow_reason,
            "component_type": component.type,
            "bbox": [x, y, x + w, y + h],
            "local_background_avg_color": bg_analysis["avg_color"],
            "selected_text_color": best_c,
            "contrast_ratio": ratio,
            "shadow_applied": add_shadow,
            "soft_surface_applied": soft_surface_applied,
            "fallback_used": not bool(palette)
        }
        
        # apply soft surface if needed
        if soft_surface_applied:
            surf_c = palette.get("soft_surface", "#00000088") if palette else "#00000088"
            surf_layer = Image.new("RGBA", (w, h), surf_c)
            # We'll merge this later. Wait, drawing happens on 'layer'.

    
    # Estimate offset/blur based on base_size to reserve space
    est_offset = int(base_size * 0.04)
    est_blur = int(base_size * 0.10)
    
    fit_w, fit_h = w, h
    if add_shadow:
        fit_w -= (est_offset + est_blur * 2)
        fit_h -= (est_offset + est_blur * 2)
        
    font_family_id = component.style.get("font_family")
    fit = fit_text(text, font_weight, base_size, fit_w, fit_h, font_family_id)
    
    # Recalculate based on final font size
    shadow_offset = int(fit["font_size"] * 0.04)
    shadow_blur = int(fit["font_size"] * 0.10)
    
    shadow_applied = False
    response_type = "none"
    if add_shadow and not fit["clipped_by_bbox"]:
        # double check if shadow fits
        if fit["final_w"] + shadow_offset + shadow_blur * 2 <= w and fit["final_h"] + shadow_offset + shadow_blur * 2 <= h:
            shadow_applied = True
            response_type = "soft_shadow"
            
    # If soft surface was decided, make background
    if kwargs.get("render_options", {}).get("enable_local_contrast_text") and locals().get("soft_surface_applied"):
        surf_c = kwargs.get("extracted_palette", {}).get("soft_surface", "#00000088")
        if len(surf_c) == 9:
            fill_tuple = tuple(int(surf_c.lstrip("#")[i:i+2], 16) for i in (0, 2, 4, 6))
        else:
            fill_tuple = (*tuple(int(surf_c.lstrip("#")[i:i+2], 16) for i in (0, 2, 4)), 180)
        layer = Image.new("RGBA", (w, h), fill_tuple)
    else:
        layer = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    
    if shadow_applied:
        shadow_layer = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        s_draw = ImageDraw.Draw(shadow_layer)
        sc = shadow_color.lstrip("#")
        sc_rgb = tuple(int(sc[i:i+2], 16) for i in (0, 2, 4))
        sc_rgba = (*sc_rgb, int(255 * shadow_opacity))
        
        cursor_y = max(0, (h - fit["final_h"]) // 2) + shadow_offset
        line_height = int(fit["font_size"] * 1.2)
        for line in fit["lines"]:
            try:
                text_w = fit["font"].getbbox(line)[2]
            except AttributeError:
                text_w = fit["font"].getsize(line)[0] if hasattr(fit["font"], "getsize") else len(line) * fit["font_size"]
            cursor_x = max(0, (w - text_w) // 2) + shadow_offset
            s_draw.text((cursor_x, cursor_y), line, font=fit["font"], fill=sc_rgba)
            cursor_y += line_height
            
        shadow_layer = shadow_layer.filter(ImageFilter.GaussianBlur(shadow_blur))
        layer.alpha_composite(shadow_layer)
        
    draw = ImageDraw.Draw(layer)
    cursor_y = max(0, (h - fit["final_h"]) // 2)
    line_height = int(fit["font_size"] * 1.2)
    for line in fit["lines"]:
        try:
            text_w = fit["font"].getbbox(line)[2]
        except AttributeError:
            text_w = fit["font"].getsize(line)[0] if hasattr(fit["font"], "getsize") else len(line) * fit["font_size"]
        cursor_x = max(0, (w - text_w) // 2)
        draw.text((cursor_x, cursor_y), line, font=fit["font"], fill=color)
        cursor_y += line_height

    diag = {
        "component_type": component.type,
        "bbox": f"{w}x{h} at ({x},{y})",
        "final_text_bbox": f"{fit['final_w']}x{fit['final_h']}",
        "font_size_final": fit["font_size"],
        "font_scaled": fit["font_scaled"],
        "truncated": fit["truncated"],
        "final_overflow_detected": fit["final_overflow_detected"],
        "clipped_by_bbox": fit["clipped_by_bbox"],
        "clipped_by_canvas": False,
        "contrast_response_applied": shadow_applied,
        "contrast_response_type": response_type
    }
    if shadow_applied:
        diag["shadow_opacity"] = shadow_opacity
        diag["shadow_offset"] = shadow_offset
        diag["shadow_blur"] = shadow_blur
        
    if locals().get("color_decision"):
        diag["color_decision"] = color_decision
        
    return layer, diag


def draw_headline_block(component: PosterComponent, image_width: int, image_height: int, **kwargs) -> tuple[Image.Image, dict]:
    return _draw_text_block_with_shadow(component, image_width, image_height, font_weight="bold", base_size_ratio=0.08, **kwargs)


def draw_subcopy_block(component: PosterComponent, image_width: int, image_height: int, **kwargs) -> tuple[Image.Image, dict]:
    # Need to handle default color correctly in the helper, but since we reuse it:
    if "text_color" not in component.style:
        component.style["text_color"] = "#E0E0E0"
    return _draw_text_block_with_shadow(component, image_width, image_height, font_weight="regular", base_size_ratio=0.04, **kwargs)


def draw_footer_panel(component: PosterComponent, image_width: int, image_height: int, **kwargs) -> tuple[Image.Image, dict]:
    x, y, w, h = component.bbox.to_pixels(image_width, image_height)
    # If soft surface was decided, make background
    if kwargs.get("render_options", {}).get("enable_local_contrast_text") and locals().get("soft_surface_applied"):
        surf_c = kwargs.get("extracted_palette", {}).get("soft_surface", "#00000088")
        if len(surf_c) == 9:
            fill_tuple = tuple(int(surf_c.lstrip("#")[i:i+2], 16) for i in (0, 2, 4, 6))
        else:
            fill_tuple = (*tuple(int(surf_c.lstrip("#")[i:i+2], 16) for i in (0, 2, 4)), 180)
        layer = Image.new("RGBA", (w, h), fill_tuple)
    else:
        layer = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)
    
    text = str(component.content)
    style = component.style
    
    bg_color = style.get("background_color", "#111827")
    text_color = style.get("text_color", "#FFFFFF")
    radius = style.get("radius", 20)
    
    draw.rounded_rectangle((0, 0, w, h), radius=radius, fill=bg_color)
    
    pad = 20
    text_max_w = max(1, w - pad * 2)
    text_max_h = max(1, h - pad * 2)
    
    base_size = style.get("font_size", int(min(image_width, image_height) * 0.03))
    font_family_id = component.style.get("font_family")
    fit = fit_text(text, "bold", base_size, text_max_w, text_max_h, font_family_id)
    
    min_readable_size = max(12, int(min(image_width, image_height) * 0.015))
    footer_readability_warning = fit["font_size"] < min_readable_size
    
    cursor_y = pad + max(0, (text_max_h - fit["final_h"]) // 2)
    line_height = int(fit["font_size"] * 1.2)
    
    for line in fit["lines"]:
        try:
            text_w = fit["font"].getbbox(line)[2]
        except AttributeError:
            text_w = fit["font"].getsize(line)[0] if hasattr(fit["font"], "getsize") else len(line) * fit["font_size"]
        cursor_x = pad + max(0, (text_max_w - text_w) // 2)
        draw.text((cursor_x, cursor_y), line, font=fit["font"], fill=text_color)
        cursor_y += line_height
        
    diag = {
        "component_type": component.type,
        "bbox": f"{w}x{h} at ({x},{y})",
        "final_text_bbox": f"{fit['final_w']}x{fit['final_h']}",
        "font_size_final": fit["font_size"],
        "font_scaled": fit["font_scaled"],
        "truncated": fit["truncated"],
        "final_overflow_detected": fit["final_overflow_detected"],
        "clipped_by_bbox": fit["clipped_by_bbox"],
        "clipped_by_canvas": False,
        "footer_readability_warning": footer_readability_warning
    }
    return layer, diag


def draw_speech_bubble(component: PosterComponent, image_width: int, image_height: int, **kwargs) -> tuple[Image.Image, dict]:
    x, y, w, h = component.bbox.to_pixels(image_width, image_height)
    # If soft surface was decided, make background
    if kwargs.get("render_options", {}).get("enable_local_contrast_text") and locals().get("soft_surface_applied"):
        surf_c = kwargs.get("extracted_palette", {}).get("soft_surface", "#00000088")
        if len(surf_c) == 9:
            fill_tuple = tuple(int(surf_c.lstrip("#")[i:i+2], 16) for i in (0, 2, 4, 6))
        else:
            fill_tuple = (*tuple(int(surf_c.lstrip("#")[i:i+2], 16) for i in (0, 2, 4)), 180)
        layer = Image.new("RGBA", (w, h), fill_tuple)
    else:
        layer = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)
    
    text = str(component.content)
    style = component.style
    
    bg_color = style.get("background_color", "#FFFFFF")
    text_color = style.get("text_color", "#111827")
    radius = style.get("radius", 30)
    tail_h = 20
    
    draw.rounded_rectangle((0, 0, w, h - tail_h), radius=radius, fill=bg_color)
    tail_coords = [
        (w // 2 - 15, h - tail_h),
        (w // 2 + 15, h - tail_h),
        (w // 2, h)
    ]
    draw.polygon(tail_coords, fill=bg_color)
    
    pad = 15
    text_max_w = max(1, w - pad * 2)
    text_max_h = max(1, h - tail_h - pad * 2)
    
    base_size = style.get("font_size", int(min(image_width, image_height) * 0.04))
    font_family_id = component.style.get("font_family")
    fit = fit_text(text, "bold", base_size, text_max_w, text_max_h, font_family_id)
    
    cursor_y = pad + max(0, (text_max_h - fit["final_h"]) // 2)
    line_height = int(fit["font_size"] * 1.2)
    
    for line in fit["lines"]:
        try:
            text_w = fit["font"].getbbox(line)[2]
        except AttributeError:
            text_w = fit["font"].getsize(line)[0] if hasattr(fit["font"], "getsize") else len(line) * fit["font_size"]
        cursor_x = pad + max(0, (text_max_w - text_w) // 2)
        draw.text((cursor_x, cursor_y), line, font=fit["font"], fill=text_color)
        cursor_y += line_height
        
    diag = {
        "component_type": component.type,
        "bbox": f"{w}x{h} at ({x},{y})",
        "final_text_bbox": f"{fit['final_w']}x{fit['final_h']}",
        "font_size_final": fit["font_size"],
        "font_scaled": fit["font_scaled"],
        "truncated": fit["truncated"],
        "final_overflow_detected": fit["final_overflow_detected"],
        "clipped_by_bbox": fit["clipped_by_bbox"],
        "clipped_by_canvas": False
    }
    return layer, diag


def draw_icon_feature_list(component: PosterComponent, image_width: int, image_height: int, **kwargs) -> tuple[Image.Image, dict]:
    x, y, w, h = component.bbox.to_pixels(image_width, image_height)
    # If soft surface was decided, make background
    if kwargs.get("render_options", {}).get("enable_local_contrast_text") and locals().get("soft_surface_applied"):
        surf_c = kwargs.get("extracted_palette", {}).get("soft_surface", "#00000088")
        if len(surf_c) == 9:
            fill_tuple = tuple(int(surf_c.lstrip("#")[i:i+2], 16) for i in (0, 2, 4, 6))
        else:
            fill_tuple = (*tuple(int(surf_c.lstrip("#")[i:i+2], 16) for i in (0, 2, 4)), 180)
        layer = Image.new("RGBA", (w, h), fill_tuple)
    else:
        layer = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)
    
    content = component.content
    style = component.style
    
    diag = {
        "component_type": component.type,
        "bbox": f"{w}x{h} at ({x},{y})",
        "final_text_bbox": "0x0",
        "font_size_final": 0,
        "font_scaled": False,
        "truncated": False,
        "final_overflow_detected": False,
        "clipped_by_bbox": False,
        "clipped_by_canvas": False,
        "item_count": 0,
        "rendered_item_count": 0,
        "list_truncated": False,
        "item_count_warning": False,
        "icon_fallback_used": False,
        "component_error": False,
        "error_message": ""
    }
    
    diag["list_readability_warning"] = False
    diag["icon_size_final"] = 0
    diag["item_gap"] = 0
    
    if not isinstance(content, list) or len(content) == 0:
        diag["component_error"] = True
        diag["error_message"] = "Invalid or empty content for icon_feature_list"
        return layer, diag
        
    total_items = len(content)
    diag["item_count"] = total_items
    
    if total_items == 1:
        diag["item_count_warning"] = True
    elif total_items > 5:
        content = content[:5]
        diag["list_truncated"] = True
        
    diag["rendered_item_count"] = len(content)
    
    bg_color = style.get("background_color", "#FFFFFF")
    text_color = style.get("text_color", "#E0E0E0")
    icon_color = style.get("icon_color", "#111827")
    
    render_opts = kwargs.get("render_options", {})
    palette = kwargs.get("extracted_palette", {})
    bg_img = kwargs.get("background_image")
    color_decision = None
    soft_surface_applied = False
    
    if render_opts.get("enable_palette_enhancement") and palette:
        # If primary_accent is too dark, use secondary_accent
        accent1 = palette.get("primary_accent", bg_color)
        accent2 = palette.get("secondary_accent", bg_color)
        # We can just use primary_accent since we filtered it to be saturated and bright enough
        bg_color = accent1
        icon_color = palette.get("dark_text_candidate", icon_color)
        
    if render_opts.get("enable_local_contrast_text") and bg_img:
        bg_analysis = analyze_bbox_background(bg_img, (x, y, x + w, y + h))
        candidates = []
        if palette:
            candidates.extend([
                palette.get("dark_text_candidate", "#2E241C"),
                palette.get("light_text_candidate", "#FFF8F0"),
                "#FFFFFF",
                "#000000"
            ])
        else:
            candidates = ["#FFFFFF", "#000000", "#333333"]
            
        best_c, ratio, needs_surface = select_best_text_color(candidates, bg_analysis["luminance"])
        text_color = best_c
        
        if needs_surface and palette:
            soft_surface_applied = True
            
        color_decision = {
            "component_type": component.type,
            "bbox": [x, y, x + w, y + h],
            "local_background_avg_color": bg_analysis["avg_color"],
            "selected_text_color": best_c,
            "selected_accent_color": bg_color,
            "color_source": "image_adaptive" if palette else "fallback",
            "contrast_ratio": ratio,
            "shadow_applied": False,
            "soft_surface_applied": soft_surface_applied,
            "fallback_used": not bool(palette)
        }
        
    # Draw soft surface if applied
    if soft_surface_applied:
        surf_c = palette.get("soft_surface", "#00000088")
        if len(surf_c) == 9:
            fill_tuple = tuple(int(surf_c.lstrip("#")[i:i+2], 16) for i in (0, 2, 4, 6))
        else:
            fill_tuple = (*tuple(int(surf_c.lstrip("#")[i:i+2], 16) for i in (0, 2, 4)), 180)
        draw.rectangle((0, 0, w, h), fill=fill_tuple)

    base_size = style.get("font_size", int(min(image_width, image_height) * 0.035))
    min_readable_size = max(16, int(min(image_width, image_height) * 0.025))
    
    allowed_icons = {"check": "✔", "star": "★", "heart": "♥", "dot": "●"}
    
    item_h = h // len(content)
    padding_y = int(item_h * 0.1)
    available_h = item_h - padding_y * 2
    
    icon_size = int(available_h * 0.72) # Decreased by ~10% for better balance
    icon_margin = int(icon_size * 0.4)
    
    diag["icon_size_final"] = icon_size
    diag["item_gap"] = padding_y * 2
    
    text_max_w = w - icon_size - icon_margin
    text_max_h = available_h
    
    cursor_y = 0
    
    max_w = 0
    font_scaled_any = False
    truncated_any = False
    clipped_any = False
    readability_warning_any = False
    
    for idx, item in enumerate(content):
        # Resolve icon
        icon_key = item.get("icon", "dot")
        if icon_key == "number":
            symbol = str(idx + 1)
        elif icon_key in allowed_icons:
            symbol = allowed_icons[icon_key]
        else:
            symbol = "●"
            diag["icon_fallback_used"] = True
            
        item_text = str(item.get("text", ""))
        
        # Fit text
        font_family_id = component.style.get("font_family")
        fit = fit_text(item_text, "regular", base_size, text_max_w, text_max_h, font_family_id)
        
        if fit["font_scaled"]: font_scaled_any = True
        if fit["truncated"]: truncated_any = True
        if fit["clipped_by_bbox"]: clipped_any = True
        if fit["font_size"] < min_readable_size: readability_warning_any = True
        
        # Draw icon background (circle)
        icon_y = cursor_y + padding_y + (available_h - icon_size) // 2
        draw.ellipse((0, icon_y, icon_size, icon_y + icon_size), fill=bg_color)
        
        # Draw icon symbol
        sym_font = load_font(size=int(icon_size * 0.6), weight="bold") or ImageFont.load_default()
        try:
            sym_w = sym_font.getbbox(symbol)[2]
            sym_h = sym_font.getbbox(symbol)[3] - sym_font.getbbox(symbol)[1]
        except AttributeError:
            sym_w = sym_font.getsize(symbol)[0] if hasattr(sym_font, "getsize") else len(symbol) * int(icon_size * 0.6)
            sym_h = sym_font.getsize(symbol)[1] if hasattr(sym_font, "getsize") else int(icon_size * 0.6)
            
        sym_x = (icon_size - sym_w) // 2
        sym_y = icon_y + (icon_size - sym_h) // 2 - int(icon_size * 0.1) # slight vertical adjustment
        draw.text((sym_x, sym_y), symbol, font=sym_font, fill=icon_color)
        
        # Draw text
        text_x = icon_size + icon_margin
        text_y = cursor_y + padding_y + (available_h - fit["final_h"]) // 2
        line_height = int(fit["font_size"] * 1.2)
        
        for line in fit["lines"]:
            draw.text((text_x, text_y), line, font=fit["font"], fill=text_color)
            text_y += line_height
            
        max_w = max(max_w, icon_size + icon_margin + fit["final_w"])
        cursor_y += item_h
        diag["font_size_final"] = fit["font_size"] # Keep last size for report
        
    diag["final_text_bbox"] = f"{max_w}x{cursor_y}"
    diag["font_scaled"] = font_scaled_any
    diag["truncated"] = truncated_any
    diag["clipped_by_bbox"] = clipped_any
    diag["final_overflow_detected"] = clipped_any
    diag["list_readability_warning"] = readability_warning_any
    
    if locals().get("color_decision"):
        diag["color_decision"] = color_decision
        
    return layer, diag


def draw_memo_card(component: PosterComponent, image_width: int, image_height: int, **kwargs) -> tuple[Image.Image, dict]:
    x, y, w, h = component.bbox.to_pixels(image_width, image_height)
    # If soft surface was decided, make background
    if kwargs.get("render_options", {}).get("enable_local_contrast_text") and locals().get("soft_surface_applied"):
        surf_c = kwargs.get("extracted_palette", {}).get("soft_surface", "#00000088")
        if len(surf_c) == 9:
            fill_tuple = tuple(int(surf_c.lstrip("#")[i:i+2], 16) for i in (0, 2, 4, 6))
        else:
            fill_tuple = (*tuple(int(surf_c.lstrip("#")[i:i+2], 16) for i in (0, 2, 4)), 180)
        layer = Image.new("RGBA", (w, h), fill_tuple)
    else:
        layer = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)
    
    content = component.content
    style = component.style
    
    diag = {
        "component_type": component.type,
        "bbox": f"{w}x{h} at ({x},{y})",
        "final_text_bbox": "0x0",
        "font_size_final": 0,
        "font_scaled": False,
        "truncated": False,
        "final_overflow_detected": False,
        "clipped_by_bbox": False,
        "clipped_by_canvas": False,
        "memo_card_truncated": False,
        "memo_card_readability_warning": False,
        "component_error": False,
        "error_message": ""
    }
    
    # Handle list truncation if multiple cards are passed
    if isinstance(content, list):
        if len(content) > 1:
            diag["memo_card_truncated"] = True
        content = content[0] if len(content) > 0 else ""
        
    text = str(content)
    if not text:
        diag["component_error"] = True
        diag["error_message"] = "Empty content for memo_card"
        return layer, diag
        
    bg_color = style.get("background_color", "#FDE68A") # Default to a soft yellow memo color
    text_color = style.get("text_color", "#111827")
    
    # Dynamic padding and radius based on BBox size
    padding = int(min(w, h) * 0.08)
    radius = int(min(w, h) * 0.10)
    
    draw.rounded_rectangle((0, 0, w, h), radius=radius, fill=bg_color)
    
    text_max_w = max(1, w - padding * 2)
    text_max_h = max(1, h - padding * 2)
    
    base_size = style.get("font_size", int(min(image_width, image_height) * 0.035))
    font_family_id = component.style.get("font_family")
    fit = fit_text(text, "regular", base_size, text_max_w, text_max_h, font_family_id)
    
    min_readable_size = max(16, int(min(image_width, image_height) * 0.02))
    if fit["font_size"] < min_readable_size:
        diag["memo_card_readability_warning"] = True
        
    cursor_y = padding + max(0, (text_max_h - fit["final_h"]) // 2)
    line_height = int(fit["font_size"] * 1.2)
    
    for line in fit["lines"]:
        try:
            text_w = fit["font"].getbbox(line)[2]
        except AttributeError:
            text_w = fit["font"].getsize(line)[0] if hasattr(fit["font"], "getsize") else len(line) * fit["font_size"]
        cursor_x = padding + max(0, (text_max_w - text_w) // 2)
        draw.text((cursor_x, cursor_y), line, font=fit["font"], fill=text_color)
        cursor_y += line_height
        
    diag["final_text_bbox"] = f"{fit['final_w']}x{fit['final_h']}"
    diag["font_size_final"] = fit["font_size"]
    diag["font_scaled"] = fit["font_scaled"]
    diag["truncated"] = fit["truncated"]
    diag["clipped_by_bbox"] = fit["clipped_by_bbox"]
    diag["final_overflow_detected"] = fit["final_overflow_detected"]
    
    return layer, diag


def draw_decorative_sticker(component: PosterComponent, image_width: int, image_height: int, **kwargs) -> tuple[Image.Image, dict]:
    x, y, w, h = component.bbox.to_pixels(image_width, image_height)
    # If soft surface was decided, make background
    if kwargs.get("render_options", {}).get("enable_local_contrast_text") and locals().get("soft_surface_applied"):
        surf_c = kwargs.get("extracted_palette", {}).get("soft_surface", "#00000088")
        if len(surf_c) == 9:
            fill_tuple = tuple(int(surf_c.lstrip("#")[i:i+2], 16) for i in (0, 2, 4, 6))
        else:
            fill_tuple = (*tuple(int(surf_c.lstrip("#")[i:i+2], 16) for i in (0, 2, 4)), 180)
        layer = Image.new("RGBA", (w, h), fill_tuple)
    else:
        layer = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)
    
    style = component.style
    sticker_type = style.get("sticker_type", "underline_accent")
    color_hex = style.get("color", "#FFD700").lstrip("#")
    
    # Calculate opacity with more conservative bounds for starburst
    if sticker_type == "starburst":
        default_opacity = 0.20
        raw_opacity = style.get("opacity", default_opacity)
        sticker_opacity = max(0.15, min(0.25, raw_opacity))
    else:
        default_opacity = 0.25
        raw_opacity = style.get("opacity", default_opacity)
        sticker_opacity = max(0.15, min(0.35, raw_opacity))
    
    color_rgb = tuple(int(color_hex[i:i+2], 16) for i in (0, 2, 4))
    color_rgba = (*color_rgb, int(255 * sticker_opacity))
    
    diag = {
        "component_type": component.type,
        "decorative_sticker_rendered": True,
        "anchor_target": style.get("anchor_target", "none"),
        "anchor_found": style.get("anchor_found", False),
        "final_bbox": style.get("final_bbox", "none"),
        "sticker_type": sticker_type,
        "sticker_opacity": sticker_opacity,
        "sticker_z_index": component.z_index,
        "sticker_clipped_by_bbox": False,
        "sticker_clipped_by_canvas": False,
        "bbox": f"{w}x{h} at ({x},{y})"
    }
    
    palette = kwargs.get("extracted_palette", {})
    diag["color_decision"] = {
        "component_type": component.type,
        "bbox": [x, y, x + w, y + h],
        "local_background_avg_color": "N/A",
        "selected_text_color": "N/A",
        "selected_accent_color": color_hex,
        "color_source": "image_adaptive" if palette else "fallback",
        "contrast_ratio": 0.0,
        "shadow_applied": False,
        "soft_surface_applied": False,
        "fallback_used": not bool(palette),
        "anchor_target": style.get("anchor_target", "none"),
        "final_bbox": style.get("final_bbox", "none")
    }
    
    try:
        if sticker_type == "underline_accent":
            # 70~90% of actual text width or fallback to 80% of bbox width
            target_text_w = style.get("target_text_width")
            if target_text_w is not None:
                # Assuming the user passes a percentage ratio of text vs bbox, or absolute pixels
                # Since we want it inside BBox, we'll bound it
                line_w = min(w, max(1, int(target_text_w * 0.85)))
            else:
                line_w = max(1, int(w * 0.8)) # Fallback
            
            line_x = (w - line_w) // 2
            
            # Thick line based on font_size equivalent or bbox height
            line_h = max(2, int(min(image_width, image_height) * 0.005))
            line_y = h - line_h
            draw.rectangle([line_x, line_y, line_x + line_w, h], fill=color_rgba)
        
        elif sticker_type == "circle_badge":
            # Draw an ellipse filling the bbox
            draw.ellipse([0, 0, w, h], fill=color_rgba)
            
        elif sticker_type == "starburst":
            # Draw a simple polygon starburst
            import math
            cx, cy = w / 2, h / 2
            outer_r = min(w, h) / 2
            inner_r = outer_r * 0.6
            points = []
            num_points = 12
            for i in range(num_points * 2):
                angle = i * math.pi / num_points
                r = outer_r if i % 2 == 0 else inner_r
                px = cx + math.cos(angle) * r
                py = cy + math.sin(angle) * r
                points.append((px, py))
            draw.polygon(points, fill=color_rgba)
    except Exception as e:
        diag["component_error"] = str(e)
        diag["decorative_sticker_rendered"] = False
        
    return layer, diag


COMPONENT_RENDERERS = {
    "headline_block": draw_headline_block,
    "subcopy_block": draw_subcopy_block,
    "footer_panel": draw_footer_panel,
    "speech_bubble": draw_speech_bubble,
    "icon_feature_list": draw_icon_feature_list,
    "memo_card": draw_memo_card,
    "decorative_sticker": draw_decorative_sticker,
}


def poster_renderer_node(state: dict[str, Any]) -> dict[str, Any]:
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
            metadata={
                "source_node": "poster_renderer",
                "render_success": False,
                "quality_pass": False,
                "layout_quality_pass": False,
            },
        )
        return {"render_result": render_result.model_dump(), "status": "failed", "error_message": "missing background image path"}

    layout_dict = state.get("poster_layout_spec") or {}
    if not layout_dict:
        layout = PosterLayoutSpec(canvas_width=1024, canvas_height=1024, components=[])
    else:
        layout = PosterLayoutSpec(**layout_dict)

    output_dir = Path("data") / "outputs" / str(state.get("job_id") or "unknown-job")
    output_dir.mkdir(parents=True, exist_ok=True)
    final_path = output_dir / "final_composite_poster.png"

    rendered_count = 0
    all_diagnostics = []
    quality_pass = True
    
    render_options = state.get("render_options", {})
    
    extracted_palette = {}
    palette_diagnostics = {}
    if render_options.get("enable_palette_enhancement"):
        try:
            with Image.open(background_path).convert("RGB") as pil_img:
                palette_diagnostics = extract_palette(pil_img)
                extracted_palette = palette_diagnostics
        except Exception as e:
            logger.warning(f"Extract palette error: {e}")
            
    with Image.open(background_path).convert("RGBA") as image:
        img_w, img_h = image.size
        sorted_components = sorted(layout.components, key=lambda c: c.z_index)
        
        text_bboxes = []
        for c in layout.components:
            if c.type != "decorative_sticker":
                c_x, c_y, c_w, c_h = c.bbox.to_pixels(img_w, img_h)
                text_bboxes.append((c_x, c_y, c_x + c_w, c_y + c_h))
        
        global_asset_diagnostics = {
            "asset_registry_used": False,
            "total_assets_requested": 0,
            "total_assets_resolved": 0,
            "asset_fallback_used": False,
            "asset_validation_warnings": []
        }
        
        # Get template_id if available
        template_id = None
        render_meta = state.get("render_result", {}).get("metadata", {}) if isinstance(state.get("render_result"), dict) else {}
        if "template_diagnostics" in render_meta:
            template_id = render_meta["template_diagnostics"].get("selected_template_id")
            
        from orchestrator.app.rendering.asset_registry import select_asset
        
        for component in sorted_components:
            renderer = COMPONENT_RENDERERS.get(component.type)
            if renderer:
                # Phase 7: Asset Manager Integration
                if component.type in ["decorative_sticker", "icon_feature_list"]:
                    global_asset_diagnostics["asset_registry_used"] = True
                    global_asset_diagnostics["total_assets_requested"] += 1
                    
                    req_asset_id = component.style.get("asset_id")
                    variant = component.style.get("sticker_type") or component.style.get("icon_type")
                    
                    asset_def, asset_diag = select_asset(
                        component_type=component.type,
                        requested_asset_id=req_asset_id,
                        variant=variant,
                        template_id=template_id
                    )
                    
                    # Store asset diagnostics to component style so it gets included in diag
                    component.style["asset_diagnostics"] = asset_diag
                    
                    if asset_def:
                        global_asset_diagnostics["total_assets_resolved"] += 1
                        # Force variant override from asset def
                        if component.type == "decorative_sticker":
                            component.style["sticker_type"] = asset_def.variant
                        elif component.type == "icon_feature_list":
                            component.style["icon_type"] = asset_def.variant
                            
                    if asset_diag.get("asset_fallback_used"):
                        global_asset_diagnostics["asset_fallback_used"] = True
                    if asset_diag.get("validation_warnings"):
                        global_asset_diagnostics["asset_validation_warnings"].extend(asset_diag.get("validation_warnings"))
                
                
                # Dynamic Anchoring for underline_accent
                sticker_type = component.style.get("sticker_type", "underline_accent")
                if component.type == "decorative_sticker" and sticker_type == "underline_accent":
                    hl_diag = next((d for d in all_diagnostics if d["component_type"] == "headline_block"), None)
                    if hl_diag:
                        # Parse headline bbox "461x307 at (102,102)"
                        import re
                        m = re.search(r'(\d+)x(\d+) at \((\d+),(\d+)\)', hl_diag.get("bbox", ""))
                        if m:
                            hl_w, hl_h, hl_x, hl_y = map(int, m.groups())
                            
                            # Parse final_text_bbox "369x240"
                            tm = re.search(r'(\d+)x(\d+)', hl_diag.get("final_text_bbox", ""))
                            if tm:
                                tw, th = map(int, tm.groups())
                            else:
                                tw, th = hl_w, hl_h
                                
                            # Calculate anchor: below the actual text within the block
                            # Assuming text is centered vertically in its block:
                            text_bottom = hl_y + (hl_h + th) // 2
                            
                            nw = int(tw * 0.45) # 45% of text width
                            nx = hl_x + (hl_w - nw) // 2
                            ny = text_bottom + 15 # 15px below the text
                            nh = int(img_h * 0.01) # height 1% of image
                            
                            component.bbox.x = nx / img_w
                            component.bbox.y = ny / img_h
                            component.bbox.w = nw / img_w
                            component.bbox.h = nh / img_h
                            
                            component.style["anchor_target"] = "headline_block"
                            component.style["anchor_found"] = True
                            component.style["final_bbox"] = f"{nw}x{nh} at ({nx},{ny})"
                            
                x, y, w, h = component.bbox.to_pixels(img_w, img_h)
                
                # Check contrast before rendering
                text_color_hex = component.style.get("text_color", "#000000").lstrip("#")
                contrast_warning = False
                contrast_ratio = 0.0
                try:
                    tc = tuple(int(text_color_hex[i:i+2], 16) for i in (0, 2, 4))
                    tc_lum = 0.299*tc[0] + 0.587*tc[1] + 0.114*tc[2]
                    
                    crop = image.crop((x, y, x+w, y+h))
                    stat = ImageStat.Stat(crop)
                    bg_lum = 0.299*stat.mean[0] + 0.587*stat.mean[1] + 0.114*stat.mean[2]
                    
                    l1 = max(tc_lum, bg_lum) / 255.0
                    l2 = min(tc_lum, bg_lum) / 255.0
                    
                    contrast_ratio = (l1 + 0.05) / (l2 + 0.05)
                    contrast_warning = contrast_ratio < 4.5
                    
                    # Decide shadow policy
                    if contrast_warning and component.type in ["headline_block", "subcopy_block"]:
                        component.style["add_soft_shadow"] = True
                        if bg_lum > 127:
                            component.style["shadow_color"] = "#000000"
                        else:
                            component.style["shadow_color"] = "#FFFFFF"
                except Exception:
                    pass
                    
                call_kwargs = {
                    "render_options": render_options,
                    "extracted_palette": extracted_palette,
                    "background_image": image,
                    "template_id": template_id,
                    "rendered_bboxes": {d["component_type"]: d for d in all_diagnostics}
                }
                layer, diag = renderer(component, img_w, img_h, **call_kwargs)
                
                # Update diag with contrast info calculated earlier
                diag["contrast_warning"] = contrast_warning
                diag["contrast_ratio"] = round(contrast_ratio, 2)
                if "contrast_response_applied" not in diag:
                    diag["contrast_response_applied"] = False
                    diag["contrast_response_type"] = "none"
                    
                # Check clipped by canvas
                if x < 0 or y < 0 or x + w > img_w or y + h > img_h:
                    diag["clipped_by_canvas"] = True
                    if component.type == "decorative_sticker":
                        diag["sticker_clipped_by_canvas"] = True
                    else:
                        diag["final_overflow_detected"] = True
                        diag["clipped_by_bbox"] = True
                        
                if component.type == "decorative_sticker":
                    overlap_found = False
                    sx1, sy1, sx2, sy2 = x, y, x + w, y + h
                    for tx1, ty1, tx2, ty2 in text_bboxes:
                        # Add a small threshold if needed, but simple overlap is fine for PoC
                        if not (sx2 <= tx1 or sx1 >= tx2 or sy2 <= ty1 or sy1 >= ty2):
                            overlap_found = True
                            break
                    diag["decorative_overlap_text"] = overlap_found
                    # Removed quality_pass = False here to keep it strictly as a diagnostic field
                
                # Check if quality failed
                if diag.get("clipped_by_bbox") and component.type != "decorative_sticker":
                    quality_pass = False
                if diag.get("final_overflow_detected") or diag.get("component_error"):
                    quality_pass = False
                    
                all_diagnostics.append(diag)
                
                # Paste the isolated layer using itself as a mask (alpha composite)
                image.alpha_composite(layer, (x, y))
                rendered_count += 1
                
        # Save as RGB to drop alpha before final output
        final_image = image.convert("RGB")
        final_image.save(final_path)

    existing_render_result = state.get("render_result", {})
    if isinstance(existing_render_result, dict):
        existing_meta = existing_render_result.get("metadata", {})
    else:
        existing_meta = getattr(existing_render_result, "metadata", {}) or {}

    new_meta = {**existing_meta}
    layout_quality_pass = quality_pass and not any(
        diag.get("final_overflow_detected")
        or diag.get("clipped_by_canvas")
        or diag.get("component_error")
        for diag in all_diagnostics
    )
    new_meta.update({
        "source_node": "poster_renderer",
        "has_text_overlay": rendered_count > 0,
        "render_success": True,
        "quality_pass": quality_pass,
        "layout_quality_pass": layout_quality_pass,
        "component_diagnostics": all_diagnostics,
        "asset_diagnostics": global_asset_diagnostics
    })

    if locals().get("palette_diagnostics"):
        new_meta["palette_diagnostics"] = palette_diagnostics
        
    color_decisions = []
    for d in all_diagnostics:
        if "color_decision" in d:
            color_decisions.append(d["color_decision"])
            del d["color_decision"]
    if color_decisions:
        new_meta["component_color_decisions"] = color_decisions

    render_result = RenderResult(
        background_image_path=str(background_path),
        final_image_path=str(final_path),
        rendered_slot_count=rendered_count,
        skipped_slot_count=0,
        warnings=[],
        metadata=new_meta,
    )
    
    artifacts = list(state.get("artifact_refs") or [])
    artifacts.append(
        {
            "type": "final_image",
            "path": str(final_path),
            "metadata": {
                "source": "poster_renderer",
                "quality_pass": quality_pass
            },
        }
    )
    
    return {
        "final_image_path": str(final_path),
        "render_result": render_result.model_dump(),
        "text_overlay_pending": False,
        "artifact_refs": artifacts,
        "status": "overlaying_text",
    }
