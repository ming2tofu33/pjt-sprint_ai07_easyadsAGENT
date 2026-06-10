from PIL import Image

from orchestrator.app.llm.nodes.safe_area_gate import safe_area_gate_node
from orchestrator.app.schemas.text_layout import ExclusionZone, FontMetric, ImageLayoutAnalysis, NormalizedBBox, TextLayoutSpec, TextSlot


def test_safe_area_gate_fails_on_image_analysis_hard_exclusion_overlap(tmp_path):
    image_path = tmp_path / "bright.png"
    Image.new("RGB", (512, 512), "#ffffff").save(image_path)
    metric = FontMetric(base_size_ratio=0.06, min_size_ratio=0.03, max_size_ratio=0.08, weight=800)
    layout = TextLayoutSpec(
        template="minimal_corner",
        canvas_width=512,
        canvas_height=512,
        slots=[TextSlot(slot_id="headline", role="headline", bbox=NormalizedBBox(x=0.10, y=0.12, w=0.36, h=0.18), font_metric=metric)],
    )
    analysis = ImageLayoutAnalysis(
        canvas_width=512,
        canvas_height=512,
        exclusion_zones=[ExclusionZone(zone_id="face_0", zone_type="face", bbox=NormalizedBBox(x=0.12, y=0.14, w=0.20, h=0.16), confidence=0.9, hard_exclusion=True, source="test")],
        luminance_summary={"left": 245},
    )

    output = safe_area_gate_node({"text_layout_spec": layout.model_dump(), "image_layout_analysis": analysis.model_dump(), "layout_refinement_result": {"selected_candidate_id": "candidate_a"}, "t2i_result": {"image_paths": [str(image_path)]}})

    report = output["safe_area_report"]
    assert report["overall_pass"] is False
    assert report["metadata"]["face_hand_overlap"] > 0
    assert report["metadata"]["contrast_risk"] is True
    assert report["metadata"]["layout_candidate_id"] == "candidate_a"


def test_safe_area_gate_uses_role_specific_product_thresholds():
    metric = FontMetric(base_size_ratio=0.04, min_size_ratio=0.02, max_size_ratio=0.06, weight=700)
    layout = TextLayoutSpec(
        template="minimal_corner",
        canvas_width=512,
        canvas_height=512,
        slots=[TextSlot(slot_id="cta", role="cta", bbox=NormalizedBBox(x=0.10, y=0.10, w=0.20, h=0.10), font_metric=metric)],
    )
    analysis = ImageLayoutAnalysis(
        canvas_width=512,
        canvas_height=512,
        exclusion_zones=[ExclusionZone(zone_id="product", zone_type="product", bbox=NormalizedBBox(x=0.10, y=0.10, w=0.04, h=0.04), confidence=0.9, hard_exclusion=True, source="test")],
    )

    output = safe_area_gate_node({"text_layout_spec": layout.model_dump(), "image_layout_analysis": analysis.model_dump()})

    assert output["safe_area_report"]["overall_pass"] is False
    assert output["safe_area_report"]["metadata"]["actual_product_overlap"] >= 0.03
