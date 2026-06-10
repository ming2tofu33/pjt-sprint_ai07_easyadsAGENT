from pathlib import Path

from PIL import Image

from orchestrator.app.llm.nodes.text_renderer import text_renderer_node
from orchestrator.app.schemas.text_layout import CopyItem, CopySpec, FontMetric, NormalizedBBox, TextLayoutSpec, TextSlot, TextStyleSpec, TypographyRule


def test_text_renderer_renders_korean_roles_with_distinct_styles(tmp_path):
    background = tmp_path / "background.png"
    Image.new("RGB", (420, 420), "#222222").save(background)
    layout = TextLayoutSpec(
        template="top_headline_center_product_bottom_cta",
        canvas_width=420,
        canvas_height=420,
        slots=[
            TextSlot(
                slot_id="headline",
                role="headline",
                bbox=NormalizedBBox(x=0.08, y=0.08, w=0.84, h=0.16),
                font_metric=FontMetric(base_size_ratio=0.07, min_size_ratio=0.04, max_size_ratio=0.10, weight=800),
                text_color="#FFFFFF",
                overlay_treatment="drop_shadow",
            ),
            TextSlot(
                slot_id="cta",
                role="cta",
                bbox=NormalizedBBox(x=0.25, y=0.78, w=0.50, h=0.10),
                font_metric=FontMetric(base_size_ratio=0.045, min_size_ratio=0.03, max_size_ratio=0.07, weight=700),
                text_color="#FFFFFF",
                overlay_treatment="plain",
            ),
        ],
    )
    style = TextStyleSpec(
        profile="clean",
        typography=TypographyRule(
            headline_font="Pretendard-Bold",
            body_font="Pretendard-Regular",
            headline_weight=800,
            body_weight=500,
            headline_size_ratio=0.07,
            body_size_ratio=0.035,
            primary_color="#111827",
            accent_color="#2563EB",
            text_color_on_light="#111827",
            text_color_on_dark="#FFFFFF",
            default_overlay="drop_shadow",
            use_text_plate=True,
        ),
    )
    state = {
        "job_id": "job_text_renderer_roles",
        "thread_id": "thread_text_renderer_roles",
        "copy_spec": CopySpec(
            items=[
                CopyItem(role="headline", text="신메뉴 출시"),
                CopyItem(role="cta", text="미리보기"),
            ]
        ).model_dump(),
        "text_layout_spec": layout.model_dump(),
        "text_style_spec": style.model_dump(),
        "t2i_result": {"image_paths": [str(background)]},
        "artifact_refs": [],
    }

    output = text_renderer_node(state)

    assert Path(output["final_image_path"]).exists()
    assert output["render_result"]["rendered_slot_count"] == 2
    assert output["text_overlay_pending"] is False


def test_text_renderer_overflow_returns_validation_preview_not_final_image(tmp_path):
    background = tmp_path / "background.png"
    Image.new("RGB", (180, 180), "#222222").save(background)
    layout = TextLayoutSpec(
        template="minimal_corner",
        canvas_width=180,
        canvas_height=180,
        slots=[
            TextSlot(
                slot_id="headline",
                role="headline",
                bbox=NormalizedBBox(x=0.05, y=0.05, w=0.18, h=0.08),
                font_metric=FontMetric(base_size_ratio=0.12, min_size_ratio=0.10, max_size_ratio=0.14, weight=800),
                text_color="#FFFFFF",
                max_lines=1,
            )
        ],
    )
    style = TextStyleSpec(
        profile="clean",
        typography=TypographyRule(
            headline_font="Pretendard-Bold",
            body_font="Pretendard-Regular",
            headline_weight=800,
            body_weight=500,
            headline_size_ratio=0.07,
            body_size_ratio=0.035,
            primary_color="#111827",
            accent_color="#2563EB",
            text_color_on_light="#111827",
            text_color_on_dark="#FFFFFF",
            default_overlay="drop_shadow",
        ),
    )
    state = {
        "job_id": "job_text_renderer_overflow",
        "copy_spec": CopySpec(items=[CopyItem(role="headline", text="This headline is intentionally far too long to fit")]).model_dump(),
        "text_layout_spec": layout.model_dump(),
        "text_style_spec": style.model_dump(),
        "t2i_result": {"image_paths": [str(background)]},
        "artifact_refs": [],
    }

    output = text_renderer_node(state)

    assert output["status"] == "failed"
    assert output["final_image_path"] is None
    assert output["artifact_refs"][-1]["type"] == "validation_preview"
    assert output["render_result"]["metadata"]["overflow_detected"] is True
