import pytest
from pydantic import ValidationError

from orchestrator.app.schemas.text_layout import (
    CopyItem,
    CopySpec,
    FontMetric,
    ImagePromptSpec,
    NormalizedBBox,
    TextLayoutSpec,
    TextSlot,
    TextStyleSpec,
    TypographyRule,
)


def _font_metric():
    return FontMetric(
        base_size_ratio=0.07,
        min_size_ratio=0.03,
        max_size_ratio=0.10,
        weight=800,
        letter_spacing_em=0.0,
        line_height_em=1.15,
    )


def _typography():
    return TypographyRule(
        headline_font="Pretendard-Bold",
        body_font="Pretendard-Regular",
        headline_weight=800,
        body_weight=400,
        headline_size_ratio=0.07,
        body_size_ratio=0.035,
        primary_color="#111111",
        accent_color="#FF0000",
        text_color_on_light="#111111",
        text_color_on_dark="#FFFFFF",
        default_overlay="drop_shadow",
        use_text_plate=False,
    )


def test_normalized_bbox_validates_bounds_and_pixels():
    bbox = NormalizedBBox(x=0.1, y=0.2, w=0.3, h=0.4)

    assert bbox.to_pixels(1000, 500) == (100, 100, 300, 200)
    assert bbox.area_ratio() == pytest.approx(0.12)
    with pytest.raises(ValidationError):
        NormalizedBBox(x=0.8, y=0.1, w=0.3, h=0.2)
    with pytest.raises(ValidationError):
        NormalizedBBox(x=0.1, y=0.8, w=0.2, h=0.3)


def test_copy_spec_requires_headline_except_no_copy():
    spec = CopySpec(items=[CopyItem(role="headline", text="오늘의 삼겹살")], copy_mode="standard")
    assert spec.get_renderable()[0].role == "headline"

    no_copy = CopySpec(items=[], copy_mode="no_copy")
    assert no_copy.get_renderable() == []
    with pytest.raises(ValidationError):
        CopySpec(items=[CopyItem(role="cta", text="예약하기")], copy_mode="standard")


def test_text_layout_spec_syncs_reserved_text_areas_from_slots():
    slot = TextSlot(slot_id="slot_headline", role="headline", bbox=NormalizedBBox(x=0.05, y=0.05, w=0.9, h=0.15), font_metric=_font_metric())
    spec = TextLayoutSpec(template="top_headline_center_product_bottom_cta", canvas_width=1080, canvas_height=1080, slots=[slot])

    assert spec.reserved_text_areas == [slot.bbox]


def test_text_style_and_image_prompt_defaults():
    style = TextStyleSpec(profile="cute", typography=_typography())
    prompt = ImagePromptSpec(
        scene_description="clean ad background",
        product_subject="cake",
        composition="reserve empty areas",
        lighting="soft light",
        target_width=1080,
        target_height=1080,
        aspect_ratio="1:1",
    )

    assert style.profile == "cute"
    assert prompt.must_not_include_text is True
