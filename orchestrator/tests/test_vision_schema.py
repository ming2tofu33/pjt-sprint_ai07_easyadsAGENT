import pytest
from pydantic import ValidationError
from typing import get_args

from orchestrator.app.schemas.vision import (
    ImageInputSpec,
    ImageMetadata,
    ImagePreprocessResult,
    ProductPreserveSpec,
    ReferenceStyleProfile,
    VisionArtifactType,
    VisionPipelineResult,
)


def _preprocess_result() -> ImagePreprocessResult:
    metadata = ImageMetadata(
        original_path="input.png",
        original_filename="input.png",
        format="PNG",
        mode="RGBA",
        width=100,
        height=80,
        file_size_bytes=123,
        has_alpha=True,
    )
    return ImagePreprocessResult(
        original_artifact_path="processed/original.png",
        preprocessed_artifact_path="processed/preprocessed.png",
        preview_path="processed/preview.png",
        width=100,
        height=80,
        mode="RGB",
        metadata=metadata,
    )


def test_vision_schemas_are_json_serializable():
    input_spec = ImageInputSpec(image_path="input.png", kind="source_product", max_side=512)
    style = ReferenceStyleProfile(
        color_palette=["#FFFFFF"],
        dominant_colors_rgb=[(255, 255, 255)],
        brightness=0.9,
        contrast_hint="low",
        mood_keywords=["bright"],
    )
    product = ProductPreserveSpec(
        source_image_path="input.png",
        preprocessed_image_path="processed/preprocessed.png",
        product_bbox={"x": 0.2, "y": 0.2, "w": 0.6, "h": 0.6},
    )
    result = VisionPipelineResult(
        input_spec=input_spec,
        preprocess_result=_preprocess_result(),
        reference_style_profile=style,
        product_preserve_spec=product,
    )

    dumped = result.model_dump(mode="json")

    assert dumped["input_spec"]["kind"] == "source_product"
    assert dumped["reference_style_profile"]["dominant_colors_rgb"] == [[255, 255, 255]]


def test_product_bbox_and_confidence_are_validated():
    with pytest.raises(ValidationError):
        ProductPreserveSpec(
            source_image_path="input.png",
            preprocessed_image_path="processed/preprocessed.png",
            product_bbox={"x": 0.7, "y": 0.2, "w": 0.5, "h": 0.6},
        )

    with pytest.raises(ValidationError):
        ProductPreserveSpec(
            source_image_path="input.png",
            preprocessed_image_path="processed/preprocessed.png",
            product_bbox={"x": 0.2, "y": 0.2, "w": 0.6, "h": 0.6},
            confidence=1.2,
        )


def test_input_spec_validates_target_size_and_max_side():
    with pytest.raises(ValidationError):
        ImageInputSpec(image_path="input.png", max_side=128)
    with pytest.raises(ValidationError):
        ImageInputSpec(image_path="input.png", target_width=0)


def test_vision_artifact_type_includes_preprocessed_preview():
    assert "preprocessed_preview" in get_args(VisionArtifactType)
