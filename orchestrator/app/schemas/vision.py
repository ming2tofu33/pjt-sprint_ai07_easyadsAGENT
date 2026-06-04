"""Vision Pipeline MVP schemas."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator


ImageInputKind = Literal["source_product", "reference_style", "store_scene", "generic_upload"]
ImagePreprocessMode = Literal["resize_only", "center_crop", "fit_with_padding"]
VisionArtifactType = Literal[
    "original_image",
    "preprocessed_image",
    "preprocessed_preview",
    "reference_image",
    "product_mask",
    "product_preview",
    "product_preserve_stub",
    "reference_style_profile",
]


class ImageInputSpec(BaseModel):
    image_path: str
    kind: ImageInputKind = "generic_upload"
    preprocess_mode: ImagePreprocessMode = "resize_only"
    max_side: int = Field(default=1536, ge=256)
    target_width: int | None = Field(default=None, gt=0)
    target_height: int | None = Field(default=None, gt=0)
    preserve_original: bool = True
    metadata: dict[str, Any] = Field(default_factory=dict)


class ImageMetadata(BaseModel):
    original_path: str
    original_filename: str | None = None
    format: str | None = None
    mode: str
    width: int
    height: int
    file_size_bytes: int | None = None
    has_alpha: bool
    exif_orientation_applied: bool = False
    metadata: dict[str, Any] = Field(default_factory=dict)


class ImagePreprocessResult(BaseModel):
    original_artifact_path: str | None = None
    preprocessed_artifact_path: str
    preview_path: str | None = None
    width: int
    height: int
    mode: str
    metadata: ImageMetadata
    warnings: list[str] = Field(default_factory=list)
    issues: list[str] = Field(default_factory=list)


class ReferenceStyleProfile(BaseModel):
    color_palette: list[str] = Field(default_factory=list)
    dominant_colors_rgb: list[tuple[int, int, int]] = Field(default_factory=list)
    brightness: float = Field(..., ge=0.0, le=1.0)
    contrast_hint: Literal["low", "medium", "high"]
    mood_keywords: list[str] = Field(default_factory=list)
    layout_hint: str | None = None
    typography_hint: str | None = None
    background_style: str | None = None
    ad_style_prompt: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class ProductPreserveSpec(BaseModel):
    source_image_path: str
    preprocessed_image_path: str
    product_bbox: dict[str, float]
    mask_path: str | None = None
    preview_path: str | None = None
    preserve_strategy: Literal["center_bbox_stub", "background_removal_future", "mask_inpaint_future", "api_edit_future"] = "center_bbox_stub"
    confidence: float = Field(default=0.3, ge=0.0, le=1.0)
    warnings: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_bbox(self):
        for key in ("x", "y", "w", "h"):
            value = self.product_bbox.get(key)
            if value is None or value < 0.0 or value > 1.0:
                raise ValueError("product_bbox x/y/w/h must be within 0.0..1.0")
        if self.product_bbox["x"] + self.product_bbox["w"] > 1.0:
            raise ValueError("product_bbox x + w must be <= 1.0")
        if self.product_bbox["y"] + self.product_bbox["h"] > 1.0:
            raise ValueError("product_bbox y + h must be <= 1.0")
        return self


class VisionPipelineResult(BaseModel):
    input_spec: ImageInputSpec
    preprocess_result: ImagePreprocessResult
    reference_style_profile: ReferenceStyleProfile | None = None
    product_preserve_spec: ProductPreserveSpec | None = None
    artifact_refs: list[dict[str, Any]] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
