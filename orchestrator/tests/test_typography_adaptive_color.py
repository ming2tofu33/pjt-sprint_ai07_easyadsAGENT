from PIL import Image

from orchestrator.app.rendering.typography_color import choose_text_color


def test_white_on_light_is_corrected_to_dark_color():
    image = Image.new("RGB", (200, 200), "#F6E8D8")
    result = choose_text_color(image, (0, 0, 200, 200), role="body", preferred="#FFFFFF")
    assert result["text_color"].lower() != "#ffffff"
    assert result["contrast_ratio"] >= 4.5


def test_dark_background_can_choose_light_text():
    image = Image.new("RGB", (200, 200), "#201712")
    result = choose_text_color(image, (0, 0, 200, 200), role="headline")
    assert result["contrast_ratio"] >= 3.0
