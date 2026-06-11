"""HTML/CSS based deterministic text renderer for TLFP."""

from __future__ import annotations

import base64
import logging
import traceback
from pathlib import Path
from typing import TYPE_CHECKING, Any

from orchestrator.app.schemas.text_layout import CopyItem, CopySpec, RenderResult, TextLayoutSpec, TextSlot, TextStyleSpec
from orchestrator.app.rendering.font_resolver import FONT_CANDIDATES, resolve_font_path
from orchestrator.app.llm.nodes.text_renderer import text_renderer_node, find_empty_half, hex_to_rgb

try:
    from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from orchestrator.app.graph.state import MarketingState

def _image_to_base64(image_path: str | Path) -> str:
    path = Path(image_path)
    with open(path, "rb") as image_file:
        encoded_string = base64.b64encode(image_file.read()).decode("utf-8")
    ext = path.suffix.lower()
    mime = "image/jpeg" if ext in {".jpg", ".jpeg"} else "image/png"
    return f"data:{mime};base64,{encoded_string}"

def find_copy_item(copy_spec: CopySpec, slot: TextSlot) -> CopyItem | None:
    renderable = copy_spec.get_renderable()
    if slot.bound_copy_id:
        suffix = slot.bound_copy_id.split(":")[-1]
        for item in renderable:
            if item.role == suffix:
                return item
    return next((item for item in renderable if item.role == slot.role), None)

def generate_html_content(
    bg_base64: str,
    layout: TextLayoutSpec,
    copy_spec: CopySpec,
    style: TextStyleSpec,
    width: int,
    height: int,
    needs_flip: bool
) -> tuple[str, list[str], int, int]:
    warnings: list[str] = []
    rendered_count = 0
    skipped_count = 0
    
    # 1. Prepare fonts
    # Find a primary local font path
    local_font_path = None
    preferred_font_family = "Pretendard, Noto Sans KR, sans-serif"
    for slot in layout.slots:
        if slot.font_metric.font_family:
            path = resolve_font_path(slot.font_metric.font_family)
            if path:
                local_font_path = path
                preferred_font_family = slot.font_metric.font_family
                break
    
    font_face_css = ""
    if local_font_path:
        # Convert local font to base64 or construct file URI
        try:
            with open(local_font_path, "rb") as f:
                b64_font = base64.b64encode(f.read()).decode("utf-8")
            font_ext = Path(local_font_path).suffix.lower().strip('.')
            format_map = {"ttf": "truetype", "otf": "opentype", "woff": "woff", "woff2": "woff2"}
            font_format = format_map.get(font_ext, "truetype")
            font_face_css = f"""
            @font-face {{
                font-family: 'LocalPrimaryFont';
                src: url('data:font/{font_format};charset=utf-8;base64,{b64_font}') format('{font_format}');
                font-weight: normal;
                font-style: normal;
            }}
            """
            preferred_font_family = "'LocalPrimaryFont', " + preferred_font_family
        except Exception as e:
            warnings.append(f"Failed to load local font to base64: {e}")

    # 2. Prepare HTML structure
    html_parts = [
        "<!DOCTYPE html>",
        "<html>",
        "<head>",
        "<meta charset='utf-8'>",
        "<style>",
        "html, body { margin: 0; padding: 0; width: 100%; height: 100%; overflow: hidden; background-color: transparent; }",
        font_face_css,
        f".container {{ position: relative; width: {width}px; height: {height}px; background-image: url('{bg_base64}'); background-size: cover; background-position: center; }}",
        ".slot { position: absolute; box-sizing: border-box; display: flex; flex-direction: column; overflow: hidden; word-break: keep-all; word-wrap: break-word; }",
        ".slot-content { display: -webkit-box; -webkit-box-orient: vertical; overflow: hidden; text-overflow: ellipsis; width: 100%; }",
        "</style>",
        "</head>",
        "<body>",
        "<div class='container'>"
    ]
    
    # 3. Process slots
    for slot in layout.slots:
        copy_item = find_copy_item(copy_spec, slot)
        if not copy_item:
            skipped_count += 1
            warnings.append(f"slot {slot.slot_id} skipped: no matching copy item")
            continue
            
        slot_x = slot.bbox.x
        slot_align = slot.alignment
        
        if needs_flip:
            slot_x = 1.0 - slot.bbox.x - slot.bbox.w
            if slot_align == "left":
                slot_align = "right"
            elif slot_align == "right":
                slot_align = "left"
                
        if slot_align == "auto":
            slot_align = "right" if slot_x > 0.5 else "left"
            
        x_px = int(slot_x * width)
        y_px = int(slot.bbox.y * height)
        w_px = int(slot.bbox.w * width)
        h_px = int(slot.bbox.h * height)
        
        # Color and overlay fallbacks for HTML
        # For a truly accurate test, we should run the same color logic as text_renderer.py.
        # But we can also use CSS to approximate or just rely on the fallback logic.
        # We will assume slot.text_color and slot.overlay_color are populated by previous nodes or we use defaults.
        text_color = getattr(slot, "text_color", None) or style.typography.primary_color
        bg_color = "transparent"
        padding = 0
        border_radius = 0
        shadow_css = ""
        
        if slot.overlay_treatment in {"solid_panel", "gradient_panel", "sticker_badge"}:
            color = getattr(slot, "overlay_color", None) or (style.typography.accent_color if slot.role == "cta" else style.typography.primary_color)
            r, g, b = hex_to_rgb(color)
            alpha = max(slot.overlay_opacity, 0.72)
            bg_color = f"rgba({r}, {g}, {b}, {alpha})"
            padding = max(10, int(min(w_px, h_px) * max(slot.inner_padding_ratio, 0.08 if slot.role == "cta" else 0.05)))
            border_radius = max(10, padding * (2 if slot.role == "cta" else 1))
            
            # Adjust box dimensions to account for padding just like PIL does
            x_px -= padding
            y_px -= padding
            w_px += padding * 2
            h_px += padding * 2

        if slot.overlay_treatment in {"drop_shadow", "stroke"}:
            # CSS drop-shadow approximation
            shadow_css = "text-shadow: 2px 2px 8px rgba(0,0,0,0.5);"
            
        align_css = "text-align: center;"
        align_items = "center"
        if slot_align == "left":
            align_css = "text-align: left;"
            align_items = "flex-start"
        elif slot_align == "right":
            align_css = "text-align: right;"
            align_items = "flex-end"
            
        # Font settings
        base_font_ratio = slot.font_metric.base_size_ratio
        role_multiplier = {
            "headline": 1.12, "subheadline": 0.86, "body": 0.74, "promotion": 0.82,
            "badge": 0.78, "cta": 0.72, "store_info": 0.66, "disclaimer": 0.55
        }.get(slot.role, 1.0)
        
        target_font_px = int(min(width, height) * base_font_ratio * role_multiplier)
        min_font_px = int(min(width, height) * slot.font_metric.min_size_ratio)
        font_weight = "bold" if slot.font_metric.weight >= 700 else "normal"
        line_height = slot.font_metric.line_height_em

        html_parts.append(f"""
        <div class="slot" id="slot-{slot.slot_id}" style="
            left: {x_px}px; top: {y_px}px; width: {w_px}px; height: {h_px}px;
            background-color: {bg_color}; padding: {padding}px; border-radius: {border_radius}px;
            align-items: {align_items}; justify-content: center;
        ">
            <div class="slot-content" style="
                font-family: {preferred_font_family};
                color: {text_color};
                {align_css}
                {shadow_css}
                font-weight: {font_weight};
                line-height: {line_height};
                -webkit-line-clamp: {slot.max_lines};
            " data-target-font="{target_font_px}" data-min-font="{min_font_px}">
                {copy_item.text.replace('<', '&lt;').replace('>', '&gt;')}
            </div>
        </div>
        """)
        rendered_count += 1
        
    html_parts.append("</div>")
    
    # 4. JavaScript for Dynamic Font Fitting
    js_fitting_script = """
    <script>
    document.fonts.ready.then(() => {
        const contents = document.querySelectorAll('.slot-content');
        contents.forEach(content => {
            const targetFont = parseInt(content.getAttribute('data-target-font'));
            const minFont = parseInt(content.getAttribute('data-min-font'));
            let currentFont = targetFont;
            
            content.style.fontSize = currentFont + 'px';
            
            const slot = content.parentElement;
            
            // Loop until it fits or reaches minFont
            // clientHeight/clientWidth vs scrollHeight/scrollWidth
            while (currentFont > minFont) {
                // If the text does not overflow vertically and horizontally
                if (content.scrollHeight <= slot.clientHeight - (parseInt(slot.style.paddingTop||0) + parseInt(slot.style.paddingBottom||0)) &&
                    content.scrollWidth <= slot.clientWidth - (parseInt(slot.style.paddingLeft||0) + parseInt(slot.style.paddingRight||0))) {
                    break;
                }
                currentFont -= 2;
                content.style.fontSize = currentFont + 'px';
            }
        });
        
        // Signal that fonts are fitted and rendering is complete
        window.renderingComplete = true;
    });
    </script>
    """
    html_parts.append(js_fitting_script)
    html_parts.append("</body></html>")
    
    return "\n".join(html_parts), warnings, rendered_count, skipped_count

def _pil_fallback(state: "MarketingState", error_msg: str) -> dict[str, Any]:
    logger.error(f"HTML Rendering failed: {error_msg}. Falling back to PIL renderer.")
    result = text_renderer_node(state)
    
    # Inject metadata identifying the fallback
    if "render_result" in result and isinstance(result["render_result"], dict):
        metadata = result["render_result"].get("metadata", {})
        metadata["requested_rendering_engine"] = "html"
        metadata["actual_rendering_engine"] = "pil_fallback"
        metadata["html_render_error"] = error_msg
        result["render_result"]["metadata"] = metadata
    
    return result

def html_text_renderer_node(state: "MarketingState") -> dict[str, Any]:
    if not PLAYWRIGHT_AVAILABLE:
        return _pil_fallback(state, "playwright package is not installed or available")
        
    result = state.get("t2i_result") or {}
    image_paths = result.get("image_paths") or []
    background_path = image_paths[0] if image_paths else None
    
    if not background_path:
        return _pil_fallback(state, "missing background image path")
        
    try:
        from PIL import Image
        with Image.open(background_path).convert("RGB") as img:
            width, height = img.size
            empty_half = find_empty_half(img)
    except Exception as e:
        return _pil_fallback(state, f"Failed to read image dimensions: {e}")

    copy_spec = CopySpec(**(state.get("copy_spec") or {}))
    layout = TextLayoutSpec(**(state.get("text_layout_spec") or {}))
    style = TextStyleSpec(**(state.get("text_style_spec") or {}))
    
    output_dir = Path("data") / "outputs" / str(state.get("job_id") or "unknown-job")
    output_dir.mkdir(parents=True, exist_ok=True)
    final_path = output_dir / "final_composite_html.png"
    
    # Calculate flip
    avg_x = 0.5
    if layout.slots:
        avg_x = sum(slot.bbox.x + slot.bbox.w / 2 for slot in layout.slots) / len(layout.slots)
    layout_is_right = avg_x > 0.5
    needs_flip = layout.auto_find_empty_space and ((layout_is_right and empty_half == "left") or (not layout_is_right and empty_half == "right"))

    try:
        bg_base64 = _image_to_base64(background_path)
        html_content, warnings, rendered_count, skipped_count = generate_html_content(
            bg_base64, layout, copy_spec, style, width, height, needs_flip
        )
        if needs_flip:
            warnings.append(f"Auto-flipped layout horizontally to match image negative space ({empty_half})")
            
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page(viewport={"width": width, "height": height})
            page.set_content(html_content, wait_until="networkidle")
            
            # Wait for our custom JS fitting script to signal completion
            page.wait_for_function("window.renderingComplete === true", timeout=5000)
            
            page.screenshot(path=str(final_path), full_page=True)
            browser.close()
            
    except PlaywrightTimeoutError as e:
        return _pil_fallback(state, f"Playwright timeout: {e}")
    except Exception as e:
        return _pil_fallback(state, f"HTML generation/Playwright error: {str(e)}\n{traceback.format_exc()}")
        
    render_result = RenderResult(
        background_image_path=str(background_path),
        final_image_path=str(final_path),
        rendered_slot_count=rendered_count,
        skipped_slot_count=skipped_count,
        warnings=warnings,
        metadata={
            "source_node": "html_text_renderer",
            "has_text_overlay": rendered_count > 0,
            "requested_rendering_engine": "html",
            "actual_rendering_engine": "html"
        },
    )
    
    artifacts = list(state.get("artifact_refs") or [])
    artifacts.append(
        {
            "type": "final_image",
            "path": str(final_path),
            "metadata": {"source": "html_text_renderer", "has_text_overlay": rendered_count > 0},
        }
    )
    
    return {
        "final_image_path": str(final_path),
        "render_result": render_result.model_dump(),
        "text_overlay_pending": False,
        "artifact_refs": artifacts,
        "status": "overlaying_text",
    }
