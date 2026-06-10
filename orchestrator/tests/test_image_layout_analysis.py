from PIL import Image, ImageDraw

from orchestrator.app.vision.layout_analysis import analyze_image_layout


def test_image_layout_analysis_returns_debug_maps_and_negative_space(tmp_path):
    image_path = tmp_path / "background.png"
    image = Image.new("RGB", (256, 256), "#eeeeee")
    draw = ImageDraw.Draw(image)
    draw.rectangle((150, 60, 230, 200), fill="#991b1b")
    image.save(image_path)

    analysis = analyze_image_layout(
        image_path,
        product_preserve_spec={"bbox": {"x": 0.58, "y": 0.22, "w": 0.30, "h": 0.56}},
        output_dir=tmp_path,
    )

    assert analysis.canvas_width == 256
    assert analysis.suggested_negative_space_regions
    assert any(zone.zone_type == "product" for zone in analysis.exclusion_zones)
    assert (tmp_path / "analysis_saliency.png").exists()
    assert (tmp_path / "analysis_edges.png").exists()
    assert (tmp_path / "analysis_exclusion_zones.png").exists()
    assert (tmp_path / "analysis_negative_space.png").exists()
