from orchestrator.app.llm.visual_templates import select_visual_template


def test_visual_template_selects_cafe_restaurant_beauty_and_fallback():
    assert select_visual_template("cafe", "instagram_feed", "premium").template_id == "cafe_dessert_soft_premium"
    assert select_visual_template("bbq", "banner", "bold").template_id == "restaurant_bbq_warm_grill"
    assert select_visual_template("beauty_salon", "instagram_story", "clean").template_id == "beauty_salon_clean_pastel"
    assert select_visual_template("unknown", "unknown", None).template_id == "generic_clean_ad_background"


def test_visual_template_uses_reference_keywords():
    template = select_visual_template(None, None, None, {"style_keywords": ["skincare", "pastel"]})

    assert template.template_id == "beauty_salon_clean_pastel"

