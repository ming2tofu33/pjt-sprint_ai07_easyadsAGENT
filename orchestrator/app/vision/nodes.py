"""LangGraph nodes for Vision Pipeline MVP preprocessing."""

from __future__ import annotations

from typing import Any

from orchestrator.app.graph.state import MarketingState, now_iso
from orchestrator.app.schemas.vision import ImageInputKind, ImagePreprocessMode
from orchestrator.app.vision.service import run_vision_pipeline_mvp


def reference_preprocess_node(state: MarketingState) -> dict[str, Any]:
    return _run_preprocess_node(state, image_key="reference_image_path", kind="reference_style")


def product_preprocess_node(state: MarketingState) -> dict[str, Any]:
    return _run_preprocess_node(state, image_key="source_image_path", kind="source_product")


def generic_image_preprocess_node(state: MarketingState) -> dict[str, Any]:
    return _run_preprocess_node(state, image_key="source_image_path", kind="generic_upload")


def _run_preprocess_node(state: MarketingState, image_key: str, kind: ImageInputKind) -> dict[str, Any]:
    image_path = state.get(image_key)
    if not image_path:
        return {
            "status": "preprocessing_image",
            "error_message": f"{image_key} is missing",
            "updated_at": now_iso(),
        }

    try:
        result = run_vision_pipeline_mvp(
            image_path=image_path,
            job_id=str(state.get("job_id") or "vision_job"),
            kind=kind,
            preprocess_mode=_normalize_preprocess_mode(state.get("vision_preprocess_mode")),
        )
    except Exception as exc:  # pragma: no cover - exact PIL/path errors are platform dependent
        current_brief = dict(state.get("current_brief") or {})
        current_brief[f"{kind}_vision_error"] = str(exc)
        return {
            "status": "failed",
            "error_message": f"vision_preprocess_failed: {exc}",
            "current_brief": current_brief,
            "updated_at": now_iso(),
        }

    result_dump = result.model_dump(mode="json")
    current_brief = dict(state.get("current_brief") or {})
    updates: dict[str, Any] = {
        "vision_pipeline_results": [*state.get("vision_pipeline_results", []), result_dump],
        "image_preprocess_result": result.preprocess_result.model_dump(mode="json"),
        "artifact_refs": [*state.get("artifact_refs", []), *result.artifact_refs],
        "current_brief": current_brief,
        "updated_at": now_iso(),
    }
    if kind == "reference_style" and result.reference_style_profile:
        updates["reference_style_profile"] = result.reference_style_profile.model_dump(mode="json")
        current_brief["reference_style_ready"] = True
        updates["status"] = "preprocessing_reference_image"
    elif kind == "source_product" and result.product_preserve_spec:
        updates["product_preserve_spec"] = result.product_preserve_spec.model_dump(mode="json")
        current_brief["product_preserve_ready"] = True
        updates["status"] = "preprocessing_product_image"
    else:
        current_brief["image_preprocess_ready"] = True
        updates["status"] = "preprocessing_image"
    return updates


def _normalize_preprocess_mode(value: str | None) -> ImagePreprocessMode:
    if value in {"resize_only", "center_crop", "fit_with_padding"}:
        return value  # type: ignore[return-value]
    return "resize_only"
