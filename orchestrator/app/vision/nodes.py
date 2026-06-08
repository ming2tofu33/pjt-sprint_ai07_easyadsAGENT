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


def _resolve_asset_to_local_file(state: MarketingState, asset_key: str, image_key: str) -> str | None:
    asset_id = state.get(asset_key)
    if not asset_id:
        return state.get(image_key)
    
    from orchestrator.app.db.repositories.assets import get_asset_by_public_id
    from orchestrator.app.storage.r2_service import download_file_from_r2
    from orchestrator.app.artifacts.service import ensure_job_output_dir
    import os
    
    workspace_id = state.get("workspace_id")
    if not workspace_id:
        raise ValueError("workspace_id is required for asset resolution")
        
    asset = get_asset_by_public_id(asset_id, workspace_id=workspace_id)
    if not asset:
        raise ValueError(f"Asset not found: {asset_id}")
        
    expected_kind = "source" if asset_key == "source_asset_id" else "reference"
    if asset.get("kind") != expected_kind:
        raise ValueError(f"Invalid asset kind: expected {expected_kind}")
        
    upload_status = (asset.get("metadata") or {}).get("upload", {}).get("status")
    if upload_status != "ready":
        raise ValueError("Asset is not ready")
    
    object_key = asset.get("object_key")
    bucket = asset.get("bucket")
    
    if not object_key or not bucket or asset.get("storage_provider") != "r2":
        raise ValueError("Asset is not valid for download")
    
    job_id = state.get("job_id") or "vision_job"
    output_dir = ensure_job_output_dir(job_id)
    ext = os.path.splitext(object_key)[1] or ".png"
    local_path = output_dir / f"{asset_key}{ext}"
    
    if not local_path.exists():
        download_file_from_r2(object_key=object_key, local_path=str(local_path), bucket=bucket)
        
    return str(local_path)


def _run_preprocess_node(state: MarketingState, image_key: str, kind: ImageInputKind) -> dict[str, Any]:
    asset_key = "source_asset_id" if image_key == "source_image_path" else "reference_asset_id"
    try:
        image_path = _resolve_asset_to_local_file(state, asset_key, image_key)
    except Exception as exc:
        return {
            "status": "failed",
            "error_message": f"asset_resolution_failed: {exc}",
            "updated_at": now_iso(),
        }

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
