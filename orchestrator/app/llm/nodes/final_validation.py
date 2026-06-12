"""Aggregate TLFP validation reports."""

from __future__ import annotations

import os
from typing import Any

from orchestrator.app.llm.metadata_builders import build_final_validation_metadata
from orchestrator.app.quality_gate.final_composite_service import evaluate_final_composite
from orchestrator.app.schemas.text_layout import FinalValidationReport


def final_validation_node(state: dict[str, Any]) -> dict[str, Any]:
    vlm_metadata_contract = build_final_validation_metadata(state)
    background = state.get("background_validation_report") or {}
    safe_area = state.get("safe_area_report") or {}
    readability = state.get("readability_report")
    no_copy = (
        state.get("copy_generation_mode") == "no_copy"
        or state.get("copy_required") is False
        or (state.get("copy_spec") or {}).get("copy_mode") == "no_copy"
    )

    warnings: list[str] = []
    issues: list[str] = []
    background_pass = bool(background.get("overall_pass"))
    safe_area_pass = bool(safe_area.get("overall_pass"))
    readability_pass = None if no_copy else bool((readability or {}).get("overall_pass"))

    if not background_pass:
        issues.append("background validation failed")
    if not safe_area_pass:
        issues.append("safe area validation failed")
    if not no_copy and readability is None:
        warnings.append("readability report is missing")
        readability_pass = False
    elif not no_copy and readability_pass is False:
        issues.append("readability validation failed")

    composite_report = evaluate_final_composite(state)
    composite_enforced = bool(state.get("render_result"))
    composite_pass = composite_report.status == "pass" or no_copy or not composite_enforced
    report = FinalValidationReport(
        overall_pass=background_pass and safe_area_pass and (True if no_copy else bool(readability_pass)) and composite_pass,
        background_pass=background_pass,
        safe_area_pass=safe_area_pass,
        readability_pass=readability_pass,
        no_copy=no_copy,
        warnings=warnings,
        issues=issues,
        metadata={
            "source_node": "final_validation",
            "ocr_or_vlm_called": bool(state.get("final_ocr_gate") or state.get("final_composite_vlm_result")),
            "vlm_call_allowed": str(os.getenv("EASYADS_VLM_ACTUAL", "")).strip().lower() in {"1", "true", "yes", "on"},
            "vlm_metadata_contract": vlm_metadata_contract,
            "validation_questions": vlm_metadata_contract["available_state"].get("validation_questions", []),
            "final_composite_quality": composite_report.public_summary,
        },
    )
    return {
        "final_validation_report": report.model_dump(),
        "final_composite_quality_report": composite_report.model_dump(),
        "status": "final_validating",
    }
