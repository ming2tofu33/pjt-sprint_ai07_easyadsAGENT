"""Analyze actual T2I output for text-safe layout regions."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from orchestrator.app.vision.layout_analysis import analyze_image_layout


def image_layout_analyzer_node(state: dict[str, Any]) -> dict[str, Any]:
    image_path = _background_path(state)
    if not image_path:
        return {"image_layout_analysis": None, "status": "background_validating"}
    output_dir = Path(image_path).parent
    analysis = analyze_image_layout(
        image_path,
        vision_pipeline_results=list(state.get("vision_pipeline_results") or []),
        product_preserve_spec=state.get("product_preserve_spec") or {},
        ocr_spans=(state.get("background_ocr_report") or {}).get("spans") or [],
        output_dir=output_dir,
    )
    return {
        "image_layout_analysis": analysis.model_dump(),
        "current_brief": {**state.get("current_brief", {}), "image_layout_analysis_ready": True},
        "status": "background_validating",
    }


def _background_path(state: dict[str, Any]) -> str | None:
    result = state.get("t2i_result") or {}
    paths = result.get("image_paths") or []
    if paths:
        return str(paths[0])
    return state.get("background_image_path") or state.get("final_image_path")
