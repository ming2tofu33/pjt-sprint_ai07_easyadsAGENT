"""Vision Pipeline MVP orchestration service."""

from __future__ import annotations

from typing import Any

from orchestrator.app.schemas.vision import ImageInputKind, ImageInputSpec, ImagePreprocessMode, VisionPipelineResult
from orchestrator.app.vision.preprocess import preprocess_image
from orchestrator.app.vision.product_preserve import build_product_preserve_rembg
from orchestrator.app.vision.reference import extract_reference_style_stub
from orchestrator.app.vision.settings import VisionSettings


def run_vision_pipeline_mvp(
    image_path: str,
    job_id: str,
    kind: ImageInputKind = "generic_upload",
    preprocess_mode: ImagePreprocessMode = "resize_only",
    target_width: int | None = None,
    target_height: int | None = None,
    settings: VisionSettings | None = None,
) -> VisionPipelineResult:
    input_spec = ImageInputSpec(
        image_path=image_path,
        kind=kind,
        preprocess_mode=preprocess_mode,
        target_width=target_width,
        target_height=target_height,
    )
    preprocess_result = preprocess_image(input_spec, job_id, settings=settings)
    reference_profile = None
    product_spec = None
    artifacts: list[dict[str, Any]] = []
    if preprocess_result.original_artifact_path:
        artifacts.append({"type": "original_image", "path": preprocess_result.original_artifact_path, "metadata": {"source": "vision_preprocess"}})
    artifacts.append({"type": "preprocessed_image", "path": preprocess_result.preprocessed_artifact_path, "metadata": {"source": "vision_preprocess"}})
    if preprocess_result.preview_path:
        artifacts.append({"type": "preprocessed_preview", "path": preprocess_result.preview_path, "metadata": {"source": "vision_preprocess"}})
    if kind == "reference_style":
        try:
            import os
            from openai import OpenAI
            from orchestrator.app.vision.vlm_extractor import extract_features_with_vlm
            
            if os.getenv("OPENAI_API_KEY"):
                client = OpenAI()
                reference_profile = extract_features_with_vlm(preprocess_result.preprocessed_artifact_path, client)
        except Exception:
            pass

        # VLM 추출 실패 시 또는 API Key가 없을 경우 기존 Stub으로 폴백(Fallback)
        if not reference_profile:
            reference_profile = extract_reference_style_stub(preprocess_result)
            
        artifacts.append({"type": "reference_style_profile", "path": preprocess_result.preprocessed_artifact_path, "metadata": reference_profile.model_dump(mode="json")})
    if kind == "source_product":
        product_spec = build_product_preserve_rembg(preprocess_result, job_id, settings=settings)
        if product_spec.mask_path:
            artifacts.append({"type": "product_mask", "path": product_spec.mask_path, "metadata": {"source": "rembg_segmentation" if product_spec.metadata.get("rembg_used") else "product_preserve_stub"}})
        if product_spec.preview_path:
            artifacts.append({"type": "product_preview", "path": product_spec.preview_path, "metadata": {"source": "rembg_segmentation" if product_spec.metadata.get("rembg_used") else "product_preserve_stub"}})
        artifacts.append({"type": "product_preserve", "path": product_spec.preprocessed_image_path, "metadata": product_spec.model_dump(mode="json")})
    return VisionPipelineResult(
        input_spec=input_spec,
        preprocess_result=preprocess_result,
        reference_style_profile=reference_profile,
        product_preserve_spec=product_spec,
        artifact_refs=artifacts,
        metadata={"stub": True, "external_model_called": False},
    )
