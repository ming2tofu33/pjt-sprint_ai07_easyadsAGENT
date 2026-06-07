"""Template-based TLFP text layout planning node."""

from __future__ import annotations

from orchestrator.app.graph.state import MarketingState
from orchestrator.app.schemas.text_layout import CopySpec, FontMetric, NormalizedBBox, TextLayoutSpec, TextSlot, TextStyleSpec


def text_layout_planner_node(state: MarketingState) -> dict[str, object]:
    copy_spec = CopySpec(**(state.get("copy_spec") or {}))
    style_spec = TextStyleSpec(**(state.get("text_style_spec") or {}))
    ad_format_spec = state.get("ad_format_spec") or {}
    ad_format = ad_format_spec.get("ad_format", "instagram_feed")
    width = int(ad_format_spec.get("width") or 1024)
    height = int(ad_format_spec.get("height") or 1024)
    template = template_for_ad_format(ad_format, copy_spec.copy_mode)
    font_metric = FontMetric(
        font_family=style_spec.typography.headline_font,
        base_size_ratio=style_spec.typography.headline_size_ratio,
        min_size_ratio=max(0.018, style_spec.typography.body_size_ratio * 0.8),
        max_size_ratio=min(0.14, style_spec.typography.headline_size_ratio * 1.2),
        weight=style_spec.typography.headline_weight,
        letter_spacing_em=style_spec.typography.letter_spacing_em,
        line_height_em=style_spec.typography.line_height_em,
    )
    layout = build_text_layout_spec(copy_spec, template, width, height, font_metric, style_spec)
    return {
        "text_layout_spec": layout.model_dump(),
        "current_brief": {**state.get("current_brief", {}), "text_layout_ready": True},
        "status": "planning_format",
    }


def template_for_ad_format(ad_format: str, copy_mode: str) -> str:
    if copy_mode == "no_copy":
        return "no_text"
    return {
        "instagram_feed": "dynamic_side_split",
        "instagram_story": "bottom_overlay_panel",
        "flyer": "multi_zone_flyer",
        "banner": "left_text_right_product",
        "product_detail": "multi_zone_flyer",
    }.get(ad_format, "top_headline_center_product_bottom_cta")


def build_text_layout_spec(copy_spec: CopySpec, template: str, width: int, height: int, font_metric: FontMetric, style_spec: TextStyleSpec) -> TextLayoutSpec:
    if template == "no_text":
        return TextLayoutSpec(template="no_text", canvas_width=width, canvas_height=height, slots=[], reserved_text_areas=[], product_zone=NormalizedBBox(x=0.15, y=0.18, w=0.70, h=0.64))
    role_boxes, product_zone = boxes_for_template(template)
    renderable_roles = {item.role for item in copy_spec.get_renderable()}
    slots: list[TextSlot] = []
    for role, bbox in role_boxes.items():
        if role not in renderable_roles:
            continue
        item = next(item for item in copy_spec.get_renderable() if item.role == role)
        slots.append(
            TextSlot(
                slot_id=f"slot_{role}",
                role=role,
                bbox=bbox,
                bound_copy_id=f"{copy_spec.spec_id}:{role}",
                rendered_text=item.text,
                font_metric=font_metric,
                alignment="auto" if template == "dynamic_side_split" else "left" if template == "left_text_right_product" else "right" if template == "right_text_left_product" else "center",
                anchor=anchor_for_role(role),
                text_color=style_spec.typography.text_color_on_dark,
                overlay_treatment=style_spec.typography.default_overlay,
                overlay_color=style_spec.typography.primary_color if style_spec.typography.use_text_plate else None,
                overlay_opacity=0.78 if style_spec.typography.use_text_plate else 0.0,
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


def anchor_for_role(role: str) -> str:
    if role == "cta":
        return "bottom_center"
    if role in {"headline", "subheadline"}:
        return "top_center"
    return "middle_center"
