from pathlib import Path

from PIL import Image

from orchestrator.app.rendering.copy_visual_validation import (
    build_copy_visual_validation_report,
    estimate_text_contrast,
    validate_text_clipping,
    validate_text_safe_area,
)


def _save_image(path: Path, color: tuple[int, int, int]):
    Image.new("RGB", (120, 120), color).save(path)


def test_dark_background_recommends_light_text(tmp_path):
    image_path = tmp_path / "dark.png"
    _save_image(image_path, (20, 18, 16))

    result = estimate_text_contrast(str(image_path), {"x": 0, "y": 0, "w": 1, "h": 1}, "#ffffff")

    assert result["background_tone"] == "dark"
    assert result["recommended_text_tone"] == "light"
    assert result["contrast_ratio_estimate"] >= 4.5


def test_bright_background_recommends_plate_or_shadow(tmp_path):
    image_path = tmp_path / "bright.png"
    _save_image(image_path, (244, 238, 232))

    result = estimate_text_contrast(str(image_path), {"x": 0, "y": 0, "w": 1, "h": 1}, "#ffffff")

    assert result["background_tone"] == "bright"
    assert result["plate_required"] is True
    assert result["shadow_required"] is True
    assert "low_text_contrast" in result["warnings"]


def test_clipping_detection_catches_text_outside_canvas():
    result = validate_text_clipping({"canvas": {"width": 100, "height": 100}, "text_boxes": [{"bbox": (80, 80, 130, 110)}]})

    assert result["text_clipping_detected"] is True
    assert "text_box_outside_canvas" in result["warnings"]


def test_safe_area_complexity_warns_for_noisy_area(tmp_path):
    image = Image.new("RGB", (120, 120), (255, 255, 255))
    pixels = image.load()
    for x in range(120):
        for y in range(120):
            pixels[x, y] = (0, 0, 0) if (x + y) % 2 == 0 else (255, 255, 255)
    image_path = tmp_path / "noisy.png"
    image.save(image_path)

    result = validate_text_safe_area(str(image_path), {"x": 0, "y": 0, "w": 1, "h": 1})

    assert result["safe_area_background_complexity"] > 0.45
    assert "safe_area_complex_background" in result["warnings"]


def test_validation_report_includes_overall_pass_and_warnings(tmp_path):
    image_path = tmp_path / "bright.png"
    _save_image(image_path, (250, 250, 250))

    result = build_copy_visual_validation_report(
        str(image_path),
        {"x": 0.1, "y": 0.1, "w": 0.5, "h": 0.5},
        "#ffffff",
        {"canvas": {"width": 120, "height": 120}, "text_boxes": []},
        min_font_size=18,
    )

    assert "overall_pass" in result
    assert "warnings" in result
    assert result["overall_pass"] is False
    assert "font_size_too_small" in result["warnings"]
