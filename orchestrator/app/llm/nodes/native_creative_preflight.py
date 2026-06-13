"""Preflight review for GPT Image 2 native prompt packages."""

from __future__ import annotations

from typing import Any

from orchestrator.app.llm.native_copy_policy import build_native_prompt_package, decide_native_typography_eligibility, validate_approved_native_copy_brief
from orchestrator.app.llm.native_creative_preflight_service import review_native_creative_preflight
from orchestrator.app.schemas.input_evidence import InputEvidenceBundle
from orchestrator.app.schemas.native_creative import ApprovedNativeCopyBrief, NativeCreativePreflightReview
from orchestrator.app.schemas.product_understanding import ProductUnderstanding


def native_creative_preflight_node(state: dict[str, Any]) -> dict[str, Any]:
    brief = ApprovedNativeCopyBrief(**(state.get("approved_native_copy_brief") or {}))
    product = state.get("product_understanding") or {}
    failures = validate_approved_native_copy_brief(brief)
    eligibility = decide_native_typography_eligibility(brief)
    input_evidence = state.get("input_evidence_bundle") or {"schema_version": "input_evidence_bundle_v1", "input_mode": "text_only", "overall_confidence": 0.0}
    package = build_native_prompt_package(
        product_understanding=product,
        copy_brief=brief,
        placement=str((state.get("ad_format_spec") or {}).get("ad_format") or "restaurant_poster"),
        preflight_status="approved" if not failures and eligibility.eligible else "rejected",
        input_evidence=input_evidence,
    )
    if failures or not eligibility.eligible:
        review = NativeCreativePreflightReview(
            decision="rejected",
            copy_grounded=bool(brief.product_evidence_ids or brief.verified_evidence_ids),
            claims_supported=not any(reason == "blocked_claim_detected" for reason in failures),
            language_natural=False,
            generic_cta_absent="generic_cta_detected" not in failures,
            text_budget_valid=not any(reason in {"text_block_limit_exceeded", "character_budget_exceeded"} for reason in failures),
            native_typography_suitable=False,
            product_visual_direction_valid=False,
            failure_reasons=failures or eligibility.blocking_reasons,
            revision_instructions=[],
        )
    else:
        review = review_native_creative_preflight(
            input_evidence=InputEvidenceBundle(**input_evidence),
            product_understanding=ProductUnderstanding(**_complete_product_understanding(product)),
            copy_brief=brief,
            prompt_package=package,
            state=state,
        )
        package = package.model_copy(update={"preflight_status": "approved" if review.decision == "approved" else "rejected"})
    decision = review.decision
    return {
        "native_typography_eligibility": eligibility.model_dump(),
        "native_creative_preflight_review": review.model_dump(),
        "native_creative_prompt_package": package.model_dump(),
        "native_generation_status": "preflight_approved" if decision == "approved" else "rejected",
    }


def _complete_product_understanding(product: dict[str, Any]) -> dict[str, Any]:
    data = dict(product or {})
    if "product_name" not in data:
        data["product_name"] = "product"
    data.setdefault("broad_category", "other")
    data.setdefault("category_path", ["other"])
    data.setdefault("confidence", 0.5)
    return data
