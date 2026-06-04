from orchestrator.app.llm.ad_format_presets import AD_FORMAT_PRESETS, build_ad_format_spec


def test_instagram_feed_preset_is_1080_square():
    spec = build_ad_format_spec("instagram_feed")

    assert spec.platform == "instagram"
    assert spec.aspect_ratio == "1:1"
    assert spec.width == 1080
    assert spec.height == 1080
    assert spec.visual_priority == "product_hero"
    assert spec.output_strategy == "generate_text_free_background_then_overlay"


def test_flyer_uses_a4_vertical_aspect_ratio():
    spec = build_ad_format_spec("flyer")

    assert spec.ad_format == "flyer"
    assert spec.aspect_ratio == "A4_vertical"
    assert spec.visual_priority == "information_first"
    assert spec.output_strategy == "multi_section_layout"


def test_banner_and_product_detail_use_pipeline_friendly_priorities():
    assert build_ad_format_spec("banner").visual_priority == "click_conversion"
    assert build_ad_format_spec("product_detail").visual_priority == "detail_explanation"


def test_required_ad_format_presets_exist():
    assert set(AD_FORMAT_PRESETS) == {
        "instagram_feed",
        "instagram_story",
        "poster",
        "flyer",
        "banner",
        "product_detail",
    }
