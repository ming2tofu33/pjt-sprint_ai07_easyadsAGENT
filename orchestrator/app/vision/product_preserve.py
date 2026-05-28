"""Product preserve placeholder artifacts for Vision Pipeline MVP."""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw

from orchestrator.app.schemas.vision import ImagePreprocessResult, ProductPreserveSpec
from orchestrator.app.vision.settings import VisionSettings, get_vision_settings


def build_product_preserve_stub(preprocess_result: ImagePreprocessResult, job_id: str, settings: VisionSettings | None = None) -> ProductPreserveSpec:
    settings = settings or get_vision_settings()
    output_dir = settings.processed_dir / safe_name(job_id)
    output_dir.mkdir(parents=True, exist_ok=True)
    with Image.open(preprocess_result.preprocessed_artifact_path).convert("RGB") as image:
        bbox = infer_center_bbox(image.width, image.height)
        mask_path = output_dir / "product_mask.png"
        preview_path = output_dir / "product_preview.png"
        build_mask(image.size, bbox).save(mask_path)
        build_preview(image, bbox).save(preview_path)
    return ProductPreserveSpec(
        source_image_path=preprocess_result.metadata.original_path,
        preprocessed_image_path=preprocess_result.preprocessed_artifact_path,
        product_bbox=bbox,
        mask_path=str(mask_path),
        preview_path=str(preview_path),
        preserve_strategy="center_bbox_stub",
        confidence=0.3,
        warnings=["center_bbox_stub_not_real_segmentation"],
        metadata={"rembg_used": False, "sam_used": False, "vlm_used": False, "stub": True},
    )


def infer_center_bbox(width: int, height: int) -> dict[str, float]:
    ratio = width / height
    if ratio < 0.8:
        return {"x": 0.15, "y": 0.20, "w": 0.70, "h": 0.55}
    if ratio > 1.25:
        return {"x": 0.25, "y": 0.15, "w": 0.50, "h": 0.70}
    return {"x": 0.20, "y": 0.20, "w": 0.60, "h": 0.60}


def build_mask(size: tuple[int, int], bbox: dict[str, float]) -> Image.Image:
    width, height = size
    mask = Image.new("L", size, 0)
    draw = ImageDraw.Draw(mask)
    draw.rectangle(to_pixels(bbox, width, height), fill=255)
    return mask


def build_preview(image: Image.Image, bbox: dict[str, float]) -> Image.Image:
    preview = image.copy().convert("RGBA")
    overlay = Image.new("RGBA", preview.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    box = to_pixels(bbox, preview.width, preview.height)
    draw.rectangle(box, outline=(255, 220, 0, 255), width=max(3, preview.width // 160))
    draw.rectangle(box, fill=(255, 220, 0, 45))
    return Image.alpha_composite(preview, overlay).convert("RGB")


def to_pixels(bbox: dict[str, float], width: int, height: int) -> tuple[int, int, int, int]:
    left = round(bbox["x"] * width)
    top = round(bbox["y"] * height)
    right = round((bbox["x"] + bbox["w"]) * width)
    bottom = round((bbox["y"] + bbox["h"]) * height)
    return left, top, right, bottom


def safe_name(value: str) -> str:
    return "".join(char if char.isalnum() or char in {"-", "_"} else "_" for char in value)[:80] or "vision_job"
