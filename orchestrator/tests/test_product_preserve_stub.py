from pathlib import Path

from PIL import Image

from orchestrator.app.schemas.vision import ImageInputSpec
from orchestrator.app.vision.preprocess import preprocess_image
from orchestrator.app.vision.product_preserve import build_product_preserve_stub
from orchestrator.app.vision.settings import VisionSettings


def test_product_preserve_stub_creates_mask_preview_and_metadata(tmp_path):
    source = tmp_path / "product.png"
    Image.new("RGB", (120, 160), (180, 120, 90)).save(source)
    settings = VisionSettings(upload_dir=tmp_path / "uploads", processed_dir=tmp_path / "processed")
    preprocess_result = preprocess_image(ImageInputSpec(image_path=str(source)), "product-stub", settings=settings)

    spec = build_product_preserve_stub(preprocess_result, "product-stub", settings=settings)

    assert spec.preserve_strategy == "center_bbox_stub"
    assert spec.confidence == 0.3
    assert spec.mask_path and Path(spec.mask_path).exists()
    assert spec.preview_path and Path(spec.preview_path).exists()
    assert spec.warnings == ["center_bbox_stub_not_real_segmentation"]
    assert spec.metadata["rembg_used"] is False
    assert spec.metadata["sam_used"] is False
    assert spec.metadata["vlm_used"] is False
    assert spec.product_bbox == {"x": 0.15, "y": 0.2, "w": 0.7, "h": 0.55}
