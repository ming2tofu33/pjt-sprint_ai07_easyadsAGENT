"""Post-image deterministic typography refinement."""

from __future__ import annotations

from typing import Any

from PIL import Image

from orchestrator.app.rendering.font_catalog import resolve_font_face
from orchestrator.app.rendering.typography_color import choose_text_color
from orchestrator.app.schemas.text_layout import TextLayoutSpec, TextStyleSpec


def adaptive_typography_refiner_node(state: dict[str, Any]) -> dict[str, Any]:
    layout = TextLayoutSpec(**(state.get("text_layout_spec") or {}))
    style = TextStyleSpec(**(state.get("text_style_spec") or {}))
    result = state.get("t2i_result") or {}
    image_paths = result.get("image_paths") or []
    background_path = image_paths[0] if image_paths else None
    warnings: list[str] = []

    if not background_path:
        return {"text_layout_spec": layout.model_dump(), "text_style_spec": style.model_dump(), "adaptive_typography_report": {"warnings": ["missing_background"]}}

    with Image.open(background_path).convert("RGB") as image:
        for slot in layout.slots:
            role_style = _role_style(style, slot.role)
            if role_style:
                face = resolve_font_face(role_style.family_id, role_style.weight)
                slot.font_metric.font_family = role_style.family_id
                slot.font_metric.weight = face.weight
                slot.font_metric.letter_spacing_em = role_style.letter_spacing_em
                slot.font_metric.line_height_em = role_style.line_height_em
                slot.font_metric.base_size_ratio = role_style.size_ratio
                slot.font_metric.min_size_ratio = role_style.min_size_ratio
                slot.font_metric.max_size_ratio = role_style.max_size_ratio
                slot.max_lines = role_style.max_lines
                slot.alignment = role_style.alignment
            bbox = slot.bbox.to_pixels(image.width, image.height)
            color = choose_text_color(image, bbox, role=slot.role, preferred=getattr(role_style, "text_color", None))
            slot.text_color = color["text_color"]
            if color["overlay_treatment"] != "none" and slot.overlay_treatment == "plain":
                slot.overlay_treatment = "solid_panel" if color["overlay_treatment"] == "content_fit_plate" else "gradient_panel"
            if slot.text_color.lower() in {"#ffffff", "#fff8ef"} and color["background"]["light_ratio"] > 0.55:
                warnings.append(f"{slot.slot_id}: corrected white-on-light risk")

    return {
        "text_layout_spec": layout.model_dump(),
        "text_style_spec": style.model_dump(),
        "adaptive_typography_report": {"source_node": "adaptive_typography_refiner", "warnings": warnings},
    }


def _role_style(style: TextStyleSpec, role: str):
    if role == "headline":
        return style.headline_style
    if role in {"subheadline", "body", "promotion", "store_info"}:
        return style.body_style
    if role == "cta":
        return style.cta_style
    if role == "price":
        return style.price_style
    if role == "disclaimer":
        return style.disclaimer_style
    if role == "badge":
        return style.label_style
    return None
