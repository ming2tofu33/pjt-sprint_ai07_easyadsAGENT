from pathlib import Path

from PIL import Image

from orchestrator.app.schemas.vision import ImageInputSpec
from orchestrator.app.vision.preprocess import preprocess_image
from orchestrator.app.vision.reference import extract_reference_style_stub
from orchestrator.app.vision.settings import VisionSettings


def test_reference_style_stub_extracts_palette_and_prompt(tmp_path):
    source = tmp_path / "reference.png"
    Image.new("RGB", (80, 80), (240, 120, 150)).save(source)
    settings = VisionSettings(upload_dir=tmp_path / "uploads", processed_dir=tmp_path / "processed")
    preprocess_result = preprocess_image(ImageInputSpec(image_path=str(source)), "ref-style", settings=settings)

    profile = extract_reference_style_stub(preprocess_result)

    assert profile.color_palette
    assert profile.dominant_colors_rgb
    assert 0.0 <= profile.brightness <= 1.0
    assert profile.contrast_hint in {"low", "medium", "high"}
    assert profile.layout_hint == "square_feed_like"
    assert profile.ad_style_prompt
    assert profile.metadata["vlm_used"] is False
    assert profile.metadata["llm_used"] is False
