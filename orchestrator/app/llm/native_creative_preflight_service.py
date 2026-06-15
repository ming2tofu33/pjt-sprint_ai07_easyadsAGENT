"""Semantic preflight for GPT Image 2 native typography packages."""

from __future__ import annotations

import json
from typing import Any

from orchestrator.app.llm.native_copy_policy import contains_request_intent, validate_approved_native_copy_brief
from orchestrator.app.llm.node_runner import run_structured_node
from orchestrator.app.schemas.input_evidence import InputEvidenceBundle
from orchestrator.app.schemas.native_creative import ApprovedNativeCopyBrief, NativeCreativePreflightReview, NativeCreativePromptPackage
from orchestrator.app.schemas.product_understanding import ProductUnderstanding


def review_native_creative_preflight(
    *,
    input_evidence: InputEvidenceBundle,
    product_understanding: ProductUnderstanding,
    copy_brief: ApprovedNativeCopyBrief,
    prompt_package: NativeCreativePromptPackage,
    state: dict[str, Any],
) -> NativeCreativePreflightReview:
    deterministic_failures = validate_approved_native_copy_brief(copy_brief)
    if deterministic_failures:
        return _review(
            decision="rejected",
            copy_brief=copy_brief,
            failures=deterministic_failures,
            provider_metadata={"provider": "deterministic", "model": None, "fallback_used": False, "token_usage": None},
        )

    prompt = (
        "Return JSON only matching NativeCreativePreflightReview. Review whether the approved native copy can be sent to GPT Image 2. "
        "Approve only if the copy is consumer-facing, contains no user request/meta instruction, transforms the user utterance when generated, keeps product identity clean, "
        "is relevant to the product, aligns with desired positioning, has supported claims, avoids generic CTA, and fits the text budget. "
        "If uncertain, return manual_review or revision_required, never approved. "
        f"USER REQUEST: {input_evidence.user_request_utterance or input_evidence.user_text}\n"
        f"PRODUCT UNDERSTANDING: {product_understanding.model_dump_json()}\n"
        f"INPUT EVIDENCE: {input_evidence.model_dump_json()}\n"
        f"COPY BRIEF: {copy_brief.model_dump_json()}\n"
        f"PROMPT PACKAGE WITHOUT FINAL PROMPT: {json.dumps(prompt_package.model_dump(exclude={'final_prompt'}), ensure_ascii=False)}"
    )

    def fallback() -> NativeCreativePreflightReview:
        failures = []
        if contains_request_intent(" ".join([copy_brief.headline or "", copy_brief.supporting_copy or "", copy_brief.closing_copy or ""])):
            failures.append("meta_instruction_leakage_detected")
        return _review(
            decision="manual_review" if not failures else "rejected",
            copy_brief=copy_brief,
            failures=failures or ["semantic_preflight_unavailable"],
            provider_metadata={"provider": "deterministic", "model": None, "fallback_used": True, "token_usage": None},
        )

    output, metadata = run_structured_node(
        dict(state),
        node_name="native_creative_preflight_review",
        output_schema=NativeCreativePreflightReview,
        prompt=prompt,
        fallback_fn=fallback,
        risk_level="high",
        confidence=0.85,
        latency_budget="standard",
        metadata={"task_name": "native_creative_preflight_review_v2", "capability": "api_full"},
    )
    review = output if isinstance(output, NativeCreativePreflightReview) else NativeCreativePreflightReview(**output)
    provider_metadata = _provider_metadata(metadata)
    if review.decision == "approved" and not _approval_fields_pass(review):
        review = review.model_copy(update={"decision": "rejected", "failure_reasons": sorted(set([*review.failure_reasons, "semantic_preflight_threshold_failed"]))})
    return review.model_copy(update={"provider_metadata": provider_metadata})


def _review(*, decision: str, copy_brief: ApprovedNativeCopyBrief, failures: list[str], provider_metadata: dict[str, Any]) -> NativeCreativePreflightReview:
    text = " ".join([copy_brief.headline or "", copy_brief.supporting_copy or "", copy_brief.closing_copy or "", copy_brief.action_cta or ""])
    no_meta = not contains_request_intent(text)
    return NativeCreativePreflightReview(
        decision=decision,  # type: ignore[arg-type]
        copy_grounded=bool(copy_brief.product_evidence_ids or copy_brief.verified_evidence_ids),
        claims_supported=not any(reason == "blocked_claim_detected" for reason in failures),
        language_natural=decision == "approved",
        generic_cta_absent="generic_cta_detected" not in failures,
        text_budget_valid=not any(reason in {"text_block_limit_exceeded", "character_budget_exceeded"} for reason in failures),
        native_typography_suitable=decision == "approved",
        product_visual_direction_valid=decision == "approved",
        consumer_facing_copy=no_meta and decision == "approved",
        meta_instruction_absent=no_meta,
        user_request_transformed="user_request_copied_as_headline" not in failures,
        product_identity_clean="product_identity_contaminated" not in failures,
        copy_relevance_score=0.0 if failures else 0.85,
        headline_quality_score=0.0 if failures else 0.8,
        positioning_alignment_score=0.0 if failures else 0.8,
        failure_reasons=sorted(set(failures)),
        revision_instructions=[],
        provider_metadata=provider_metadata,
    )


def _approval_fields_pass(review: NativeCreativePreflightReview) -> bool:
    return (
        review.consumer_facing_copy
        and review.meta_instruction_absent
        and review.user_request_transformed
        and review.product_identity_clean
        and review.copy_relevance_score >= 0.80
        and review.headline_quality_score >= 0.75
        and review.positioning_alignment_score >= 0.75
        and review.generic_cta_absent
        and review.text_budget_valid
    )


def _provider_metadata(metadata: dict[str, Any]) -> dict[str, Any]:
    result = metadata.get("llm_call_result") or {}
    selection = metadata.get("model_selection") or result.get("model_selection") or {}
    return {
        "provider": result.get("provider") or metadata.get("provider") or selection.get("provider"),
        "model": result.get("model_name") or selection.get("model_name") or selection.get("provider_profile") or "gpt-5.4",
        "fallback_used": bool(metadata.get("fallback_used")),
        "fallback_reason": metadata.get("fallback_reason"),
        "token_usage": result.get("token_usage"),
        "task_name": "native_creative_preflight_review_v2",
    }
