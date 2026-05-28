from pathlib import Path

from PIL import Image

from orchestrator.app.vision.service import run_vision_pipeline_mvp
from orchestrator.app.vision.settings import VisionSettings


def _settings(tmp_path: Path) -> VisionSettings:
    return VisionSettings(upload_dir=tmp_path / "uploads", processed_dir=tmp_path / "processed")


def _image(path: Path) -> Path:
    Image.new("RGB", (100, 80), (220, 180, 120)).save(path)
    return path


def test_vision_service_reference_style_result(tmp_path):
    result = run_vision_pipeline_mvp(str(_image(tmp_path / "ref.png")), "svc-ref", kind="reference_style", settings=_settings(tmp_path))

    assert result.reference_style_profile is not None
    assert result.product_preserve_spec is None
    assert any(artifact["type"] == "reference_style_profile" for artifact in result.artifact_refs)
    assert result.metadata["external_model_called"] is False


def test_vision_service_product_preserve_result(tmp_path):
    result = run_vision_pipeline_mvp(str(_image(tmp_path / "product.png")), "svc-product", kind="source_product", settings=_settings(tmp_path))

    assert result.product_preserve_spec is not None
    assert result.reference_style_profile is None
    assert any(artifact["type"] == "product_mask" for artifact in result.artifact_refs)
    assert any(artifact["type"] == "product_preview" for artifact in result.artifact_refs)
