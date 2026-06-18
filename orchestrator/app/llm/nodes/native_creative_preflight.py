"""Preflight review for GPT Image 2 native prompt packages."""

from __future__ import annotations

from typing import Any

from orchestrator.app.graph.state import read_model, resolve_requested_ad_format
from orchestrator.app.llm.native_copy_policy import (
    build_native_prompt_package,
    decide_native_typography_eligibility,
    new_native_generation_budget,
    resolve_visible_text_source_by_format,
    validate_approved_native_copy_brief,
)
from orchestrator.app.llm.native_creative_preflight_service import review_native_creative_preflight
from orchestrator.app.schemas.input_evidence import InputEvidenceBundle
from orchestrator.app.schemas.native_creative import (
    ApprovedNativeCopyBrief,
    NativeCreativePreflightReview,
)
from orchestrator.app.schemas.product_understanding import ProductUnderstanding


def native_creative_preflight_node(state: dict[str, Any]) -> dict[str, Any]:
    brief = read_model(state, "approved_native_copy_brief", ApprovedNativeCopyBrief)
    product = state.get("product_understanding") or {}
    input_evidence = state.get("input_evidence_bundle") or {"schema_version": "input_evidence_bundle_v1", "input_mode": "text_only", "overall_confidence": 0.0}

    ad_format = resolve_requested_ad_format(state) or ""

    # Task 7: format-specific plan isolation. Extended visible text is authorized
    # only through the matching isolated plan; contamination / conflict / missing
    # required plan fails closed before any prompt package is produced.
    isolation = resolve_visible_text_source_by_format(
        ad_format=ad_format,
        flyer_approved_copy_plan=state.get("flyer_approved_copy_plan"),
        flyer_promotional_approved_copy_plan=state.get("flyer_promotional_approved_copy_plan"),
        product_detail_approved_feature_plan=state.get("product_detail_approved_feature_plan"),
    )
    if isolation.status == "fail":
        return _isolation_failed_result(state, brief, product, input_evidence, isolation)

    failures = validate_approved_native_copy_brief(brief)
    eligibility = decide_native_typography_eligibility(brief)
    # Exact user-approved copy is authoritative and is not re-judged by the
    # generated-copy heuristics (same rule as the brief stage). Generated copy
    # still must clear validation + eligibility.
    brief_ok = brief.copy_source_mode == "user_exact" or (not failures and eligibility.eligible)
    # Task 8: the package carries only the matching format's visible text + grammar.
    package = build_native_prompt_package(
        product_understanding=product,
        copy_brief=brief,
        placement=str((state.get("ad_format_spec") or {}).get("ad_format") or "restaurant_poster"),
        preflight_status="approved" if brief_ok else "rejected",
        input_evidence=input_evidence,
        ad_format=ad_format,
        product_detail_approved_feature_plan=state.get("product_detail_approved_feature_plan"),
        flyer_approved_copy_plan=state.get("flyer_approved_copy_plan"),
        flyer_promotional_approved_copy_plan=state.get("flyer_promotional_approved_copy_plan"),
    )
    if not brief_ok:
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
        if brief.copy_source_mode == "user_exact":
            review = NativeCreativePreflightReview(
                decision="approved",
                copy_grounded=True,
                claims_supported=True,
                language_natural=True,
                generic_cta_absent=True,
                text_budget_valid=True,
                native_typography_suitable=True,
                product_visual_direction_valid=True,
                consumer_facing_copy=True,
                meta_instruction_absent=True,
                user_request_transformed=True,
                product_identity_clean=True,
                copy_relevance_score=1.0,
                headline_quality_score=1.0,
                positioning_alignment_score=1.0,
                failure_reasons=[],
                revision_instructions=[],
                provider_metadata={"provider": "deterministic", "model": None, "fallback_used": False, "token_usage": None},
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
        "native_generation_budget": new_native_generation_budget(request_fingerprint=package.prompt_sha256).model_dump(),
        "native_generation_status": "preflight_approved" if decision == "approved" else "rejected",
    }


def _isolation_failed_result(state: dict[str, Any], brief, product: dict[str, Any], input_evidence, isolation) -> dict[str, Any]:
    """Fail closed on format contamination: never emit an approved package."""
    package = build_native_prompt_package(
        product_understanding=product,
        copy_brief=brief,
        placement=str((state.get("ad_format_spec") or {}).get("ad_format") or "restaurant_poster"),
        preflight_status="manual_review" if isolation.decision == "manual_review" else "rejected",
        input_evidence=input_evidence,
    )
    review = NativeCreativePreflightReview(
        decision="manual_review" if isolation.decision == "manual_review" else "rejected",
        copy_grounded=bool(brief.product_evidence_ids or brief.verified_evidence_ids),
        claims_supported=True,
        language_natural=False,
        generic_cta_absent=True,
        text_budget_valid=True,
        native_typography_suitable=False,
        product_visual_direction_valid=False,
        failure_reasons=list(isolation.failure_codes),
        revision_instructions=[],
    )
    return {
        "native_creative_preflight_review": review.model_dump(),
        "native_creative_prompt_package": package.model_dump(),
        "native_generation_status": isolation.decision,
    }


def _complete_product_understanding(product: dict[str, Any]) -> dict[str, Any]:
    data = dict(product or {})
    if "product_name" not in data:
        data["product_name"] = "product"
    data.setdefault("broad_category", "other")
    data.setdefault("category_path", ["other"])
    data.setdefault("confidence", 0.5)
    return data
