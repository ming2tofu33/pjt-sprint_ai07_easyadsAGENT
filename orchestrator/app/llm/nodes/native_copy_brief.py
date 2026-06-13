"""Native copy brief graph node."""

from __future__ import annotations

from typing import Any

from orchestrator.app.llm.native_copy_brief_service import generate_approved_native_copy_brief
from orchestrator.app.schemas.input_evidence import InputEvidenceBundle
from orchestrator.app.schemas.native_creative import CreativeExecutionPlan
from orchestrator.app.schemas.product_understanding import ProductUnderstanding


def native_copy_brief_node(state: dict[str, Any]) -> dict[str, Any]:
    plan = CreativeExecutionPlan(**(state.get("creative_execution_plan") or {}))
    evidence = InputEvidenceBundle(**(state.get("input_evidence_bundle") or {}))
    understanding = ProductUnderstanding(**(state.get("product_understanding") or {}))
    brief = generate_approved_native_copy_brief(
        input_evidence=evidence,
        product_understanding=understanding,
        execution_plan=plan,
        source_visual_analysis=state.get("native_source_visual_analysis"),
        state=state,
    )
    return {"approved_native_copy_brief": brief.model_dump(), "native_generation_status": "copy_approved" if brief.compliance_status == "approved" else brief.compliance_status}
