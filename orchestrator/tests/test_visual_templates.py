from orchestrator.app.llm.visual_templates import select_visual_template


def test_visual_template_exact_business_type_selection():
    assert select_visual_template("cafe", "instagram_feed", "premium").template_id == "cafe_dessert_soft_premium"
    assert select_visual_template("restaurant_bbq", "banner", "bold").template_id == "restaurant_bbq_warm_grill"
    assert select_visual_template("restaurant", "instagram_feed", "clean").template_id == "restaurant_generic_clean"
    assert select_visual_template("beauty_skincare", "instagram_story", "clean").template_id == "beauty_salon_clean_pastel"
    assert select_visual_template("beauty_hair", "instagram_story", "clean").template_id == "beauty_salon_clean_pastel"
    assert select_visual_template("beauty_nail", "instagram_story", "clean").template_id == "beauty_salon_clean_pastel"
    assert select_visual_template("beauty_spa", "instagram_story", "clean").template_id == "beauty_salon_clean_pastel"


def test_visual_template_fails_closed_for_raw_or_ambiguous_values():
    assert select_visual_template("bbq", "banner", "bold").template_id == "generic_clean_ad_background"
    assert select_visual_template("beauty_salon", "instagram_story", "clean").template_id == "generic_clean_ad_background"
    assert select_visual_template("korean cafe restaurant", "instagram_feed", "premium").template_id == "generic_clean_ad_background"
    assert select_visual_template("unknown", "unknown", None).template_id == "generic_clean_ad_background"


def test_visual_template_does_not_infer_domain_from_reference_keywords():
    template = select_visual_template(None, None, None, {"style_keywords": ["skincare", "pastel"]})
    assert template.template_id == "generic_clean_ad_background"
