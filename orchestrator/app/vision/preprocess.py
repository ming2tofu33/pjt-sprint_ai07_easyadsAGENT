"""PIL-only image preprocessing for Vision Pipeline MVP."""

from __future__ import annotations

import shutil
from pathlib import Path

from PIL import Image, ImageOps

from orchestrator.app.schemas.vision import ImageInputSpec, ImageMetadata, ImagePreprocessResult
from orchestrator.app.vision.settings import VisionSettings, get_vision_settings


def preprocess_image(input_spec: ImageInputSpec, job_id: str, settings: VisionSettings | None = None) -> ImagePreprocessResult:
    settings = settings or get_vision_settings()
    source = Path(input_spec.image_path).expanduser().resolve()
    output_dir = (settings.processed_dir / safe_name(job_id)).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    issues: list[str] = []
    warnings: list[str] = []

    if not source.exists():
        raise FileNotFoundError(f"image_path does not exist: {input_spec.image_path}")
    if source.suffix.lower() not in settings.allowed_extensions:
        raise ValueError(f"unsupported image extension: {source.suffix}")
    file_size = source.stat().st_size
    if file_size > settings.max_file_size_mb * 1024 * 1024:
        raise ValueError("image file exceeds max_file_size_mb")

    original_artifact_path: str | None = None
    if input_spec.preserve_original:
        original_target = output_dir / f"original{source.suffix.lower()}"
        shutil.copy2(source, original_target)
        original_artifact_path = str(original_target)

    with Image.open(source) as opened:
        original_format = opened.format
        original_mode = opened.mode
        has_alpha = "A" in opened.getbands()
        image = ImageOps.exif_transpose(opened)
        exif_applied = image.size != opened.size
        if image.width * image.height > settings.max_image_pixels:
            raise ValueError("image exceeds max_image_pixels")
        rgb_image = image.convert("RGB")
        processed = apply_preprocess(rgb_image, input_spec, settings)

    preprocessed_path = output_dir / "preprocessed.png"
    processed.save(preprocessed_path)
    preview_path = None
    if settings.save_preview:
        preview = resize_max_side(processed.copy(), settings.preview_max_side)
        preview_file = output_dir / "preview.png"
        preview.save(preview_file)
        preview_path = str(preview_file)

    metadata = ImageMetadata(
        original_path=str(source),
        original_filename=source.name,
        format=original_format,
        mode=original_mode,
        width=processed.width,
        height=processed.height,
        file_size_bytes=file_size,
        has_alpha=has_alpha,
        exif_orientation_applied=exif_applied,
        metadata={"preprocess_mode": input_spec.preprocess_mode, "stub": False},
    )
    return ImagePreprocessResult(
        original_artifact_path=original_artifact_path,
        preprocessed_artifact_path=str(preprocessed_path),
        preview_path=preview_path,
        width=processed.width,
        height=processed.height,
        mode="RGB",
        metadata=metadata,
        warnings=warnings,
        issues=issues,
    )


def apply_preprocess(image: Image.Image, input_spec: ImageInputSpec, settings: VisionSettings) -> Image.Image:
    max_side = input_spec.max_side or settings.default_max_side
    if input_spec.preprocess_mode == "center_crop" and input_spec.target_width and input_spec.target_height:
        return center_crop(image, input_spec.target_width, input_spec.target_height)
    if input_spec.preprocess_mode == "fit_with_padding" and input_spec.target_width and input_spec.target_height:
        return fit_with_padding(image, input_spec.target_width, input_spec.target_height)
    return resize_max_side(image, max_side)


def resize_max_side(image: Image.Image, max_side: int) -> Image.Image:
    if max(image.size) <= max_side:
        return image
    image.thumbnail((max_side, max_side), Image.Resampling.LANCZOS)
    return image


def center_crop(image: Image.Image, target_width: int, target_height: int) -> Image.Image:
    source_ratio = image.width / image.height
    target_ratio = target_width / target_height
    if source_ratio > target_ratio:
        new_width = int(image.height * target_ratio)
        left = (image.width - new_width) // 2
        cropped = image.crop((left, 0, left + new_width, image.height))
    else:
        new_height = int(image.width / target_ratio)
        top = (image.height - new_height) // 2
        cropped = image.crop((0, top, image.width, top + new_height))
    return cropped.resize((target_width, target_height), Image.Resampling.LANCZOS)


def fit_with_padding(image: Image.Image, target_width: int, target_height: int) -> Image.Image:
    canvas = Image.new("RGB", (target_width, target_height), (245, 245, 242))
    fitted = image.copy()
    fitted.thumbnail((target_width, target_height), Image.Resampling.LANCZOS)
    left = (target_width - fitted.width) // 2
    top = (target_height - fitted.height) // 2
    canvas.paste(fitted, (left, top))
    return canvas


def safe_name(value: str) -> str:
    return "".join(char if char.isalnum() or char in {"-", "_"} else "_" for char in value)[:80] or "vision_job"
