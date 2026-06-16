"""Product preserve placeholder artifacts for Vision Pipeline MVP."""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw

from orchestrator.app.schemas.vision import ImagePreprocessResult, ProductPreserveSpec
from orchestrator.app.vision.settings import VisionSettings, get_vision_settings
from orchestrator.app.vision.adapters.vision_service_client import get_product_mask

def build_product_preserve_rembg(preprocess_result: ImagePreprocessResult, job_id: str, settings: VisionSettings | None = None) -> ProductPreserveSpec:
    settings = settings or get_vision_settings()
    output_dir = settings.processed_dir / safe_name(job_id)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    input_path = preprocess_result.preprocessed_artifact_path
    mask_path = output_dir / "product_mask_rembg.png"
    preview_path = output_dir / "product_preview_rembg.png"
    
    # 1. vision-service API 호출을 통해 마스크 추출 시도
    success = get_product_mask(input_path, str(mask_path))
    
    # 2. 통신 실패 등 에러 시 안전하게 기존 Stub으로 폴백 (Fallback)
    if not success:
        return build_product_preserve_stub(preprocess_result, job_id, settings)
    
    # 3. 추출된 실제 마스크에서 BBox(바운딩 박스) 계산
    with Image.open(mask_path).convert("L") as mask:
        bbox_pixels = mask.getbbox()
        
        # 배경만 있어서 박스를 그릴 수 없는 경우도 폴백
        if not bbox_pixels:
            return build_product_preserve_stub(preprocess_result, job_id, settings)
            
        left, top, right, bottom = bbox_pixels
        width = mask.width
        height = mask.height
        
        normalized_bbox = {
            "x": left / width,
            "y": top / height,
            "w": (right - left) / width,
            "h": (bottom - top) / height,
        }
        
    # 4. 프리뷰 이미지 생성
    with Image.open(input_path).convert("RGB") as image:
        build_preview(image, normalized_bbox).save(preview_path)
        
    return ProductPreserveSpec(
        source_image_path=preprocess_result.metadata.original_path,
        preprocessed_image_path=input_path,
        product_bbox=normalized_bbox,
        mask_path=str(mask_path),
        preview_path=str(preview_path),
        preserve_strategy="rembg_api",
        confidence=0.85,
        warnings=[],
        metadata={"rembg_used": True, "sam_used": False, "vlm_used": False, "stub": False},
    )

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
