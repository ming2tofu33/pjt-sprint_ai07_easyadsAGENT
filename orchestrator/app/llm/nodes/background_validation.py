"""Rule-based background validation for TLFP mock outputs."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from PIL import Image

from orchestrator.app.graph.state import MarketingState
from orchestrator.app.llm.metadata_builders import build_background_validation_metadata
from orchestrator.app.schemas.text_layout import BackgroundValidationReport


def _metadata_from_t2i_request(state: MarketingState) -> dict[str, Any]:
    request = state.get("t2i_request") or {}
    return dict(request.get("metadata") or {})


def _reserved_text_areas(state: MarketingState) -> list[dict[str, Any]]:
    metadata = _metadata_from_t2i_request(state)
    return (
        metadata.get("reserved_text_areas")
        or (state.get("image_prompt_spec") or {}).get("reserved_text_areas")
        or (state.get("text_layout_spec") or {}).get("reserved_text_areas")
        or []
    )


def background_validation_node(state: MarketingState) -> dict[str, Any]:
    result = state.get("t2i_result") or {}
    request = state.get("t2i_request") or {}
    image_paths = result.get("image_paths") or []
    image_path = image_paths[0] if image_paths else None
    expected_width = request.get("width")
    expected_height = request.get("height")
    metadata = _metadata_from_t2i_request(state)
    render_text_in_image = bool(metadata.get("render_text_in_image", False))
    reserved_areas = _reserved_text_areas(state)
    vlm_metadata_contract = build_background_validation_metadata(state)

    warnings: list[str] = []
    issues: list[str] = []
    width: int | None = None
    height: int | None = None
    image_exists = bool(image_path and Path(image_path).exists())

    if not image_path:
        issues.append("missing image path")
    elif not image_exists:
        issues.append("background image file does not exist")
    else:
        try:
            with Image.open(image_path) as image:
                width, height = image.size
        except Exception as exc:  # pragma: no cover - defensive corruption path
            issues.append(f"failed to open background image: {exc}")

    if width and height and expected_width and expected_height:
        if abs(width - int(expected_width)) > 2 or abs(height - int(expected_height)) > 2:
            warnings.append("background dimensions differ from requested dimensions")
    if render_text_in_image:
        issues.append("render_text_in_image must remain false for TLFP background generation")
    if state.get("copy_generation_mode") != "no_copy" and state.get("copy_required", True) and not reserved_areas:
        warnings.append("reserved text areas are missing for text overlay workflow")

    report = BackgroundValidationReport(
        overall_pass=not issues,
        image_exists=image_exists,
        image_path=image_path,
        width=width,
        height=height,
        expected_width=expected_width,
        expected_height=expected_height,
        render_text_in_image=render_text_in_image,
        reserved_text_area_count=len(reserved_areas),
        text_artifact_check="not_run",
        watermark_check="not_run",
        warnings=warnings,
        issues=issues,
        metadata={
            "source_node": "background_validation",
            "ocr_or_vlm_called": False,
            "vlm_call_allowed": False,
            "vlm_metadata_contract": vlm_metadata_contract,
            "validation_questions": vlm_metadata_contract["available_state"].get("validation_questions", []),
        },
    )
    artifacts = list(state.get("artifact_refs") or [])
    if image_path:
        artifacts.append(
            {
                "type": "background_image",
                "path": image_path,
                "metadata": {"source": "t2i_generation"},
            }
        )
    return {
        "background_validation_report": report.model_dump(),
        "artifact_refs": artifacts,
        "status": "background_validating",
    }
