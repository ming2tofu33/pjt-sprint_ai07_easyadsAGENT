"""Template-based TLFP text layout planning node."""

from __future__ import annotations

from orchestrator.app.graph.state import read_model, write_model
from orchestrator.app.schemas.text_layout import CopySpec, CopyVisualIntent, FontMetric, NormalizedBBox, TextLayoutSpec, TextSlot, TextStyleSpec


def text_layout_planner_node(state: dict[str, object]) -> dict[str, object]:
    copy_spec = read_model(state, "copy_spec", CopySpec)
    style_spec = read_model(state, "text_style_spec", TextStyleSpec)
    intent = read_model(state, "copy_visual_intent", CopyVisualIntent, default=None)
    ad_format_spec = state.get("ad_format_spec") or {}
    ad_format = ad_format_spec.get("ad_format", "instagram_feed")
    width = int(ad_format_spec.get("width") or 1024)
    height = int(ad_format_spec.get("height") or 1024)
    template = template_for_ad_format(ad_format, copy_spec.copy_mode, intent)
    font_metric = FontMetric(
        font_family=style_spec.typography.headline_font,
        base_size_ratio=style_spec.typography.headline_size_ratio,
        min_size_ratio=max(0.018, style_spec.typography.body_size_ratio * 0.8),
        max_size_ratio=min(0.14, style_spec.typography.headline_size_ratio * 1.2),
        weight=style_spec.typography.headline_weight,
        letter_spacing_em=style_spec.typography.letter_spacing_em,
        line_height_em=style_spec.typography.line_height_em,
    )
    layout = build_text_layout_spec(copy_spec, template, width, height, font_metric, style_spec, intent)
    return {
        "text_layout_spec": write_model(layout),
        "current_brief": {**state.get("current_brief", {}), "text_layout_ready": True},
        "status": "planning_format",
    }


def template_for_ad_format(ad_format: str, copy_mode: str, intent: CopyVisualIntent | None = None) -> str:
    if copy_mode == "no_copy":
        return "no_text"
    if intent and intent.reference_layout_hint:
        hinted = template_from_reference_hint(intent.reference_layout_hint)
        if hinted:
            return hinted
    if intent and intent.product_text_relationship == "centered_minimal":
        return "centered_hero"
    if intent and intent.product_text_relationship == "top_bottom":
        return "top_headline_center_product_bottom_cta"
    if intent and intent.hierarchy in {"editorial_product", "menu_showcase", "minimal_premium"}:
        return "left_text_right_product"
    if intent and intent.hierarchy == "conversion":
        if ad_format == "instagram_story":
            return "bottom_overlay_panel"
    return {
        "instagram_feed": "dynamic_side_split",
        "instagram_story": "bottom_overlay_panel",
        "flyer": "multi_zone_flyer",
        "banner": "left_text_right_product",
        "product_detail": "multi_zone_flyer",
    }.get(ad_format, "top_headline_center_product_bottom_cta")


def build_text_layout_spec(copy_spec: CopySpec, template: str, width: int, height: int, font_metric: FontMetric, style_spec: TextStyleSpec, intent: CopyVisualIntent | None = None) -> TextLayoutSpec:
    if template == "no_text":
        return TextLayoutSpec(template="no_text", canvas_width=width, canvas_height=height, slots=[], reserved_text_areas=[], product_zone=NormalizedBBox(x=0.15, y=0.18, w=0.70, h=0.64))
    role_boxes, product_zone = boxes_for_template(template)
    renderable_roles = {item.role for item in copy_spec.get_renderable()}
    slots: list[TextSlot] = []
    for role, bbox in role_boxes.items():
        if role not in renderable_roles:
            continue
        item = next(item for item in copy_spec.get_renderable() if item.role == role)
        
        overlay_treatment = style_spec.typography.default_overlay
        if role == "cta":
            cta_mode = copy_spec.metadata.get("cta_mode", "text")
            if cta_mode == "button":
                overlay_treatment = "solid_panel"
            else:
                overlay_treatment = "plain" if overlay_treatment == "solid_panel" else overlay_treatment
                
        slots.append(
            TextSlot(
                slot_id=f"slot_{role}",
                role=role,
                bbox=bbox,
                bound_copy_id=f"{copy_spec.spec_id}:{role}",
                rendered_text=item.text,
                font_metric=font_metric,
                alignment=alignment_for_role(role, template, intent),
                anchor=anchor_for_role(role, intent),
                text_color=style_spec.typography.text_color_on_dark,
                overlay_treatment=overlay_treatment if role == "cta" else overlay_for_role(role, style_spec, intent),
                overlay_color=overlay_color_for_role(role, style_spec, intent),
                overlay_opacity=overlay_opacity_for_role(role, style_spec, intent),
                max_lines=2 if role == "headline" else 3,
            )
        )
    return TextLayoutSpec(
        template=template, 
        canvas_width=width, 
        canvas_height=height, 
        slots=slots, 
        product_zone=product_zone,
        auto_find_empty_space=(template == "dynamic_side_split")
    )


def overlay_for_role(role: str, style_spec: TextStyleSpec, intent: CopyVisualIntent | None) -> str:
    if role == "cta" and intent:
        if intent.cta_style in {"text_link", "none"}:
            return "plain"
        if intent.cta_style in {"small_label", "pill_button", "solid_button"}:
            return "solid_panel"
    return style_spec.typography.default_overlay


def template_from_reference_hint(hint: str) -> str | None:
    normalized = hint.lower()
    if "left text" in normalized and "right product" in normalized:
        return "left_text_right_product"
    if "right text" in normalized and "left product" in normalized:
        return "right_text_left_product"
    if "bottom" in normalized and "overlay" in normalized:
        return "bottom_overlay_panel"
    if "center" in normalized and "minimal" in normalized:
        return "centered_hero"
    return None


def alignment_for_role(role: str, template: str, intent: CopyVisualIntent | None) -> str:
    if template == "dynamic_side_split":
        return "auto"
    if intent and intent.preferred_alignment in {"left", "center", "right"}:
        return intent.preferred_alignment
    if template == "left_text_right_product":
        return "left"
    if template == "right_text_left_product":
        return "right"
    return "center"


def overlay_color_for_role(role: str, style_spec: TextStyleSpec, intent: CopyVisualIntent | None) -> str | None:
    if intent and intent.plate_policy == "none":
        return None
    if role == "cta" and intent and intent.plate_policy == "cta_only":
        return style_spec.typography.accent_color
    return style_spec.typography.primary_color if style_spec.typography.use_text_plate else None


def overlay_opacity_for_role(role: str, style_spec: TextStyleSpec, intent: CopyVisualIntent | None) -> float:
    if intent and intent.plate_policy == "none":
        return 0.0
    if role == "cta" and intent and intent.cta_style in {"small_label", "pill_button", "solid_button"}:
        return 0.82
    return 0.78 if style_spec.typography.use_text_plate else 0.0


def boxes_for_template(template: str) -> tuple[dict[str, NormalizedBBox], NormalizedBBox]:
    if template == "left_text_right_product":
        return (
            {
                "headline": NormalizedBBox(x=0.06, y=0.12, w=0.42, h=0.20),
                "subheadline": NormalizedBBox(x=0.06, y=0.35, w=0.40, h=0.16),
                "cta": NormalizedBBox(x=0.06, y=0.72, w=0.32, h=0.10),
            },
            NormalizedBBox(x=0.52, y=0.10, w=0.42, h=0.80),
        )
    if template in ("right_text_left_product", "dynamic_side_split"):
        return (
            {
                "headline": NormalizedBBox(x=0.52, y=0.12, w=0.42, h=0.20),
                "subheadline": NormalizedBBox(x=0.54, y=0.35, w=0.40, h=0.16),
                "cta": NormalizedBBox(x=0.62, y=0.72, w=0.32, h=0.10),
            },
            NormalizedBBox(x=0.06, y=0.10, w=0.42, h=0.80),
        )
    if template == "multi_zone_flyer":
        return (
            {
                "headline": NormalizedBBox(x=0.06, y=0.05, w=0.88, h=0.14),
                "promotion": NormalizedBBox(x=0.08, y=0.22, w=0.35, h=0.10),
                "price": NormalizedBBox(x=0.55, y=0.22, w=0.37, h=0.10),
                "body": NormalizedBBox(x=0.08, y=0.72, w=0.84, h=0.12),
                "subheadline": NormalizedBBox(x=0.08, y=0.72, w=0.84, h=0.12),
                "cta": NormalizedBBox(x=0.12, y=0.87, w=0.76, h=0.08),
            },
            NormalizedBBox(x=0.10, y=0.34, w=0.80, h=0.34),
        )
    if template == "bottom_overlay_panel":
        return (
            {
                "headline": NormalizedBBox(x=0.08, y=0.66, w=0.84, h=0.13),
                "subheadline": NormalizedBBox(x=0.10, y=0.79, w=0.80, h=0.07),
                "cta": NormalizedBBox(x=0.28, y=0.88, w=0.44, h=0.07),
            },
            NormalizedBBox(x=0.12, y=0.12, w=0.76, h=0.48),
        )
    return (
        {
            "headline": NormalizedBBox(x=0.05, y=0.06, w=0.90, h=0.18),
            "subheadline": NormalizedBBox(x=0.10, y=0.25, w=0.80, h=0.08),
            "cta": NormalizedBBox(x=0.30, y=0.86, w=0.40, h=0.08),
        },
        NormalizedBBox(x=0.15, y=0.36, w=0.70, h=0.42),
    )


def anchor_for_role(role: str, intent: CopyVisualIntent | None = None) -> str:
    if intent and intent.preferred_alignment == "left":
        return "bottom_left" if role == "cta" else "top_left"
    if intent and intent.preferred_alignment == "right":
        return "bottom_right" if role == "cta" else "top_right"
    if role == "cta":
        return "bottom_center"
    if role in {"headline", "subheadline"}:
        return "top_center"
    return "middle_center"
