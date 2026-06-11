from orchestrator.app.llm.nodes.post_t2i_layout_refiner import post_t2i_layout_refiner_node
from orchestrator.app.schemas.text_layout import (
    CopyItem,
    CopySpec,
    CopyVisualIntent,
    ExclusionZone,
    FontMetric,
    ImageLayoutAnalysis,
    NormalizedBBox,
    TextLayoutSpec,
    TextSlot,
    TextStyleSpec,
    TypographyRule,
)


def _style() -> TextStyleSpec:
    return TextStyleSpec(
        profile="clean",
        typography=TypographyRule(
            headline_font="Pretendard",
            body_font="Pretendard",
            headline_weight=800,
            body_weight=500,
            headline_size_ratio=0.06,
            body_size_ratio=0.034,
            primary_color="#111827",
            accent_color="#b91c1c",
            text_color_on_light="#111827",
            text_color_on_dark="#ffffff",
            default_overlay="solid_panel",
        ),
    )


def _intent() -> CopyVisualIntent:
    return CopyVisualIntent(hierarchy="conversion", headline_emphasis="large_bold", body_density="low", cta_visibility="required", cta_style="pill_button", preferred_alignment="adaptive", typography_mood="clean_sans", plate_policy="content_fit", product_text_relationship="text_over_negative_space")


def _fallback_layout() -> TextLayoutSpec:
    metric = FontMetric(base_size_ratio=0.06, min_size_ratio=0.03, max_size_ratio=0.08, weight=800)
    return TextLayoutSpec(template="minimal_corner", canvas_width=1024, canvas_height=1024, slots=[TextSlot(slot_id="headline", role="headline", bbox=NormalizedBBox(x=0.06, y=0.10, w=0.36, h=0.16), font_metric=metric)])


def test_post_t2i_layout_refiner_selects_image_aware_candidate_away_from_product():
    copy = CopySpec(items=[CopyItem(role="headline", text="딸기라떼 신메뉴"), CopyItem(role="cta", text="지금 보기")])
    analysis = ImageLayoutAnalysis(
        canvas_width=1024,
        canvas_height=1024,
        exclusion_zones=[ExclusionZone(zone_id="product", zone_type="product", bbox=NormalizedBBox(x=0.56, y=0.10, w=0.35, h=0.75), confidence=0.9, hard_exclusion=True, source="test")],
        suggested_negative_space_regions=[NormalizedBBox(x=0.06, y=0.12, w=0.40, h=0.62)],
        edge_density_summary={"left": 0.03, "center": 0.30, "right": 0.45},
        local_variance_summary={"left": 0.03, "center": 0.30, "right": 0.45},
        saliency_summary={"left": 0.02, "center": 0.25, "right": 0.60},
        luminance_summary={"left": 120, "center": 140, "right": 170},
        analysis_confidence=0.8,
    )
    state = {"copy_spec": copy.model_dump(), "text_style_spec": _style().model_dump(), "copy_visual_intent": _intent().model_dump(), "image_layout_analysis": analysis.model_dump(), "text_layout_spec": _fallback_layout().model_dump()}

    output = post_t2i_layout_refiner_node(state)

    assert output["layout_refinement_result"]["action"] in {"render", "reduce_information"}
    assert output["text_layout_spec"]["slots"][0]["bbox"]["x"] < 0.5
    assert output["layout_candidate_scores"]


def test_post_t2i_layout_refiner_manual_review_when_analysis_missing_and_copy_does_not_fit():
    copy = CopySpec(items=[CopyItem(role="headline", text="copy_123 ... 너무 긴 문장입니다 너무 긴 문장입니다 너무 긴 문장입니다")])
    state = {"copy_spec": copy.model_dump(), "text_style_spec": _style().model_dump(), "text_layout_spec": _fallback_layout().model_dump()}

    output = post_t2i_layout_refiner_node(state)

    assert output["layout_refinement_result"]["action"] == "manual_review"
    assert output["layout_copy_fit_report"]["rewrite_required"] is True
