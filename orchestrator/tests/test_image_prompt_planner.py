from orchestrator.app.llm.nodes.image_prompt_planner import build_deterministic_image_prompt_spec
from orchestrator.app.schemas.text_layout import NormalizedBBox, TextLayoutSpec


def _state(business_type: str, reference_template: dict | None = None) -> dict:
    layout = TextLayoutSpec(
        template="top_headline_center_product_bottom_cta",
        canvas_width=1024,
        canvas_height=1024,
        reserved_text_areas=[NormalizedBBox(x=0.08, y=0.08, w=0.84, h=0.16)],
        slots=[],
    )
    return {
        "context": {"business_type": business_type, "item_or_service": "대표 상품", "brand_tone": "premium"},
        "ad_format_spec": {"width": 1024, "height": 1024, "aspect_ratio": "1:1", "ad_format": "instagram_feed"},
        "text_layout_spec": layout.model_dump(),
        "text_style_spec": {"profile": "premium"},
        "selected_reference_template": reference_template or {},
    }


def test_image_prompt_uses_visual_template_and_safety_terms():
    spec = build_deterministic_image_prompt_spec(_state("cafe"))

    assert spec.metadata["visual_template_id"] == "cafe_dessert_soft_premium"
    assert "Reserve clean negative space for Korean text overlay" in spec.positive_prompt_en
    negative = spec.negative_prompt_en.lower()
    for term in ["text", "letters", "numbers", "hangul", "korean characters", "logo", "watermark", "typography", "caption", "signage"]:
        assert term in negative
    assert spec.must_not_include_text is True
    assert spec.reserved_text_areas


def test_image_prompt_template_selection_variants():
    assert build_deterministic_image_prompt_spec(_state("restaurant")).metadata["visual_template_id"] == "restaurant_bbq_warm_grill"
    assert build_deterministic_image_prompt_spec(_state("beauty")).metadata["visual_template_id"] == "beauty_salon_clean_pastel"
    assert build_deterministic_image_prompt_spec(_state("unknown")).metadata["visual_template_id"] == "generic_clean_ad_background"


def test_image_prompt_keeps_reference_template_hint():
    reference = {"title": "Pastel Beauty", "style_keywords": ["skincare"], "layout_hint": "clean_text_space"}
    spec = build_deterministic_image_prompt_spec(_state("unknown", reference))

    assert spec.metadata["selected_reference_template"]["title"] == "Pastel Beauty"
    assert "Pastel Beauty" in spec.positive_prompt_en
