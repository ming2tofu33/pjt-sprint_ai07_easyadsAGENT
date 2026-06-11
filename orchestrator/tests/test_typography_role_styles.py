from orchestrator.app.llm.nodes.text_style_binder import build_role_styles


def test_role_styles_separate_headline_body_and_cta_hierarchy():
    styles = build_role_styles(
        {
            "preset_id": "editorial_serif_sans",
            "headline_family_id": "ridi_batang",
            "body_family_id": "pretendard",
            "cta_family_id": "pretendard",
            "headline_weight": 400,
            "body_weight": 400,
            "cta_weight": 500,
            "headline_scale": "display_large",
            "body_scale": "body_small",
            "headline_tracking": "tight",
            "body_tracking": "normal",
            "headline_leading": "compact",
            "body_leading": "relaxed",
            "cta_treatment": "editorial_underline",
        }
    )
    assert styles["headline"].family_id != styles["body"].family_id
    assert styles["headline"].size_ratio / styles["body"].size_ratio >= 1.7
    assert styles["headline"].size_ratio / styles["cta"].size_ratio >= 1.5
    assert styles["cta"].overlay_treatment == "editorial_underline"
