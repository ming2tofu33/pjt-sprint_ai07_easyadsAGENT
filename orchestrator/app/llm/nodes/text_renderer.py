"""Deterministic PIL text renderer for TLFP."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFont

from orchestrator.app.graph.state import MarketingState
from orchestrator.app.schemas.text_layout import CopyItem, CopySpec, RenderResult, TextLayoutSpec, TextSlot, TextStyleSpec


SYSTEM_FONT_CANDIDATES = [
    "C:/Windows/Fonts/malgun.ttf",
    "C:/Windows/Fonts/malgunbd.ttf",
    "C:/Windows/Fonts/arial.ttf",
    "/System/Library/Fonts/AppleSDGothicNeo.ttc",
    "/Library/Fonts/AppleGothic.ttf",
    "/usr/share/fonts/truetype/nanum/NanumGothic.ttf",
    "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/opentype/unifont/unifont.otf",
]


def text_renderer_node(state: MarketingState) -> dict[str, Any]:
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
        draw = ImageDraw.Draw(image, "RGBA")
        for slot in layout.slots:
            copy_item = find_copy_item(copy_spec, slot)
            if not copy_item:
                skipped_count += 1
                warnings.append(f"slot {slot.slot_id} skipped: no matching copy item")
                continue
            x, y, w, h = slot.bbox.to_pixels(image.width, image.height)
            font_size = estimate_font_size(slot, image.width, image.height)
            font, font_warning = load_font(slot, font_size)
            if font_warning:
                warnings.append(font_warning)
            lines = wrap_text(copy_item.text, max_chars=max(4, int(w / max(font_size * 0.55, 1))), max_lines=slot.max_lines)
            draw_overlay(draw, slot, x, y, w, h, style)
            draw_wrapped_text(draw, lines, slot, font, x, y, w, h)
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
    minimum = int(min(canvas_w, canvas_h) * slot.font_metric.min_size_ratio)
    maximum = int(min(canvas_w, canvas_h) * slot.font_metric.max_size_ratio)
    return max(18, min(maximum, max(minimum, base)))


def load_font(slot: TextSlot, size: int) -> tuple[ImageFont.FreeTypeFont | ImageFont.ImageFont, str | None]:
    candidates = [slot.font_metric.font_path] if slot.font_metric.font_path else []
    candidates.extend(SYSTEM_FONT_CANDIDATES)
    for candidate in candidates:
        if candidate and Path(candidate).exists():
            try:
                return ImageFont.truetype(candidate, size=size), None
            except Exception:
                continue
    return ImageFont.load_default(), f"slot {slot.slot_id} used default PIL font fallback"


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
    if len(lines) == max_lines and len(" ".join(words)) > len(" ".join(lines)):
        lines[-1] = lines[-1].rstrip(". ") + "..."
    return lines or [text[:max_chars]]


def draw_overlay(draw: ImageDraw.ImageDraw, slot: TextSlot, x: int, y: int, w: int, h: int, style: TextStyleSpec) -> None:
    treatment = slot.overlay_treatment
    if treatment not in {"solid_panel", "gradient_panel", "sticker_badge", "blur_backdrop"}:
        return
    color = slot.overlay_color or style.typography.primary_color
    r, g, b = hex_to_rgb(color)
    alpha = int(255 * max(slot.overlay_opacity, 0.65))
    pad = int(min(w, h) * slot.inner_padding_ratio)
    draw.rounded_rectangle((x - pad, y - pad, x + w + pad, y + h + pad), radius=max(8, pad), fill=(r, g, b, alpha))


def draw_wrapped_text(draw: ImageDraw.ImageDraw, lines: list[str], slot: TextSlot, font: ImageFont.ImageFont, x: int, y: int, w: int, h: int) -> None:
    fill = hex_to_rgb(slot.text_color) + (255,)
    line_height = int(getattr(font, "size", 18) * slot.font_metric.line_height_em)
    total_h = line_height * len(lines)
    cursor_y = y + max(0, (h - total_h) // 2)
    for line in lines:
        bbox = draw.textbbox((0, 0), line, font=font)
        text_w = bbox[2] - bbox[0]
        if slot.alignment == "left":
            cursor_x = x
        elif slot.alignment == "right":
            cursor_x = x + max(0, w - text_w)
        else:
            cursor_x = x + max(0, (w - text_w) // 2)
        if slot.overlay_treatment in {"drop_shadow", "stroke"}:
            draw.text((cursor_x + 2, cursor_y + 2), line, font=font, fill=(0, 0, 0, 150))
        draw.text((cursor_x, cursor_y), line, font=font, fill=fill)
        cursor_y += line_height


def hex_to_rgb(value: str) -> tuple[int, int, int]:
    cleaned = value.strip().lstrip("#")
    if len(cleaned) != 6:
        return (255, 255, 255)
    return tuple(int(cleaned[index : index + 2], 16) for index in (0, 2, 4))
