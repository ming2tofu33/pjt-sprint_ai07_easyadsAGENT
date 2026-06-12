"""Preflight review for GPT Image 2 native prompt packages."""

from __future__ import annotations

from typing import Any

from orchestrator.app.llm.native_copy_policy import build_native_prompt_package, decide_native_typography_eligibility, validate_approved_native_copy_brief
from orchestrator.app.schemas.native_creative import ApprovedNativeCopyBrief, NativeCreativePreflightReview


def native_creative_preflight_node(state: dict[str, Any]) -> dict[str, Any]:
    brief = ApprovedNativeCopyBrief(**(state.get("approved_native_copy_brief") or {}))
    product = state.get("product_understanding") or {}
    failures = validate_approved_native_copy_brief(brief)
    eligibility = decide_native_typography_eligibility(brief)
    decision = "approved" if not failures and eligibility.eligible else "rejected"
    review = NativeCreativePreflightReview(
        decision=decision,
        copy_grounded=bool(brief.verified_evidence_ids or product.get("product_name")),
        claims_supported=not any(reason == "blocked_claim_detected" for reason in failures),
        language_natural=brief.language in {"korean", "mixed", "english"},
        generic_cta_absent="generic_cta_detected" not in failures,
        text_budget_valid=not any(reason in {"text_block_limit_exceeded", "character_budget_exceeded"} for reason in failures),
        native_typography_suitable=eligibility.eligible,
        product_visual_direction_valid=True,
        failure_reasons=failures,
        revision_instructions=[],
    )
    package = build_native_prompt_package(product_understanding=product, copy_brief=brief, placement=str((state.get("ad_format_spec") or {}).get("ad_format") or "restaurant_poster"), preflight_status="approved" if decision == "approved" else "rejected")
    return {
        "native_typography_eligibility": eligibility.model_dump(),
        "native_creative_preflight_review": review.model_dump(),
        "native_creative_prompt_package": package.model_dump(),
        "native_generation_status": "preflight_approved" if decision == "approved" else "rejected",
    }
