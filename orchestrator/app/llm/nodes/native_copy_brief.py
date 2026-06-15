"""Native copy brief graph node."""

from __future__ import annotations

from typing import Any

from orchestrator.app.graph.state import read_model, resolve_requested_ad_format
from orchestrator.app.llm.format_approved_plan_service import build_format_approved_plan_bundle
from orchestrator.app.llm.native_copy_brief_service import generate_approved_native_copy_brief
from orchestrator.app.schemas.input_evidence import InputEvidenceBundle
from orchestrator.app.schemas.native_creative import CreativeExecutionPlan
from orchestrator.app.schemas.product_understanding import ProductUnderstanding


def native_copy_brief_node(state: dict[str, Any]) -> dict[str, Any]:
    plan = read_model(state, "creative_execution_plan", CreativeExecutionPlan)
    evidence = read_model(state, "input_evidence_bundle", InputEvidenceBundle)
    understanding = read_model(state, "product_understanding", ProductUnderstanding)
    brief = generate_approved_native_copy_brief(
        input_evidence=evidence,
        product_understanding=understanding,
        execution_plan=plan,
        source_visual_analysis=state.get("native_source_visual_analysis"),
        state=state,
    )

    result: dict[str, Any] = {
        "approved_native_copy_brief": brief.model_dump(),
        "format_approved_plan_bundle": None,
        # Format isolation: each turn writes only its own extended plan, never
        # leaking another format's plan into state.
        "flyer_approved_copy_plan": None,
        "flyer_promotional_approved_copy_plan": None,
        "product_detail_approved_feature_plan": None,
    }

    if brief.compliance_status != "approved":
        result["native_generation_status"] = brief.compliance_status
        return result

    ad_format = resolve_requested_ad_format(state) or ""
    bundle = build_format_approved_plan_bundle(
        ad_format=ad_format,
        input_evidence=evidence,
        product_understanding=understanding,
        approved_copy=brief,
        state=state,
    )
    result["format_approved_plan_bundle"] = bundle.model_dump()
    if bundle.flyer_approved_copy_plan is not None:
        result["flyer_approved_copy_plan"] = bundle.flyer_approved_copy_plan.model_dump()
    if bundle.flyer_promotional_approved_copy_plan is not None:
        result["flyer_promotional_approved_copy_plan"] = bundle.flyer_promotional_approved_copy_plan.model_dump()
    if bundle.product_detail_approved_feature_plan is not None:
        result["product_detail_approved_feature_plan"] = bundle.product_detail_approved_feature_plan.model_dump()

    # Fail closed: a required extended plan that is not approved must not proceed
    # to typography planning / preflight / image generation as if the two-block
    # brief were sufficient.
    if bundle.decision in {"approved", "not_required"}:
        result["native_generation_status"] = "copy_approved"
    else:
        result["native_generation_status"] = bundle.decision

    return result
