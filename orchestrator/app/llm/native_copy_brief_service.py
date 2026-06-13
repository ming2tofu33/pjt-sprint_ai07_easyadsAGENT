"""GPT-5.4 native copy brief service."""

from __future__ import annotations

import json
import time
from typing import Any

from orchestrator.app.llm.native_copy_candidate_service import generate_native_copy_strategy_bundle
from orchestrator.app.llm.native_copy_policy import validate_approved_native_copy_brief
from orchestrator.app.schemas.input_evidence import InputEvidenceBundle
from orchestrator.app.schemas.native_creative import ApprovedNativeCopyBrief, CreativeExecutionPlan, NativeCopyStrategyBundle
from orchestrator.app.schemas.product_understanding import ProductUnderstanding


def generate_approved_native_copy_brief(
    *,
    input_evidence: InputEvidenceBundle,
    product_understanding: ProductUnderstanding,
    execution_plan: CreativeExecutionPlan,
    source_visual_analysis: dict | None,
    state: dict[str, Any],
) -> ApprovedNativeCopyBrief:
    adapter = state.get("native_copy_adapter")
    if adapter:
        payload = adapter.generate_native_copy_brief(input_evidence=input_evidence, product_understanding=product_understanding, execution_plan=execution_plan, source_visual_analysis=source_visual_analysis, state=state)
    elif state.get("native_copy_strategy_bundle"):
        return _brief_from_strategy_bundle(NativeCopyStrategyBundle(**state["native_copy_strategy_bundle"]), input_evidence=input_evidence, product_understanding=product_understanding)
    else:
        bundle = generate_native_copy_strategy_bundle(input_evidence=input_evidence, product_understanding=product_understanding, source_visual_analysis=source_visual_analysis, state=state)
        return _brief_from_strategy_bundle(bundle, input_evidence=input_evidence, product_understanding=product_understanding)
    copy_payload = payload.get("approved_native_copy_brief") or payload.get("copy_brief") or payload.get("copy") or payload.get("native_copy") or payload
    brief = ApprovedNativeCopyBrief(
        **_coerce_native_copy_payload(
            copy_payload,
            input_evidence=input_evidence,
            product_understanding=product_understanding,
            provider_metadata=payload.get("provider_metadata") or {},
        )
    )
    failures = validate_approved_native_copy_brief(brief)
    if failures:
        return brief.model_copy(update={"compliance_status": "rejected", "rejection_reasons": sorted(set([*brief.rejection_reasons, *failures]))})
    return brief


def _brief_from_strategy_bundle(
    bundle: NativeCopyStrategyBundle,
    *,
    input_evidence: InputEvidenceBundle,
    product_understanding: ProductUnderstanding,
) -> ApprovedNativeCopyBrief:
    candidate = next((item for item in bundle.candidates if item.candidate_id == bundle.recommended_candidate_id), None)
    scorecard = next((item for item in bundle.scorecards if item.candidate_id == bundle.recommended_candidate_id), None)
    if candidate is None or scorecard is None or scorecard.blocked:
        return ApprovedNativeCopyBrief(
            headline=None,
            supporting_copy=None,
            language="korean",
            message_role="headline_only",
            allowed_texts=[],
            forbidden_texts=[],
            max_text_blocks=1,
            max_total_characters=48,
            verified_evidence_ids=product_understanding.product_name_evidence_ids,
            unsupported_claim_categories=[],
            compliance_status="rejected",
            rejection_reasons=bundle.revision_reasons or ["no_unblocked_candidate"],
            copy_source_mode="generated",
            source_user_request=input_evidence.user_request_utterance or input_evidence.user_text,
            non_display_instructions=input_evidence.non_display_instruction_fragments,
            product_identity=product_understanding.product_name,
            desired_positioning=input_evidence.desired_positioning or product_understanding.desired_positioning,
            campaign_intent=input_evidence.campaign_intent or product_understanding.campaign_intent,
            transformation_performed=False,
            product_evidence_ids=product_understanding.product_name_evidence_ids,
            positioning_realization_plan=bundle.positioning_plan.model_dump(),
            alternative_candidate_summaries=[_candidate_summary(item, bundle) for item in bundle.candidates],
            campaign_message_plan=dict(getattr(bundle, "campaign_message_plan", {}) or {}),
            support_basis_type="none",
        )
    texts = [candidate.headline, candidate.supporting_copy or candidate.closing_copy]
    texts = [text for text in texts if text]
    brief = ApprovedNativeCopyBrief(
        headline=candidate.headline,
        supporting_copy=candidate.supporting_copy,
        closing_copy=candidate.closing_copy if not candidate.supporting_copy else None,
        action_cta=None,
        language=candidate.language,
        message_role="headline_plus_support" if candidate.supporting_copy else ("headline_plus_closing" if candidate.closing_copy else "headline_only"),
        allowed_texts=texts,
        forbidden_texts=list(input_evidence.non_display_instruction_fragments),
        max_text_blocks=len(texts),
        max_total_characters=48,
        verified_evidence_ids=list(dict.fromkeys([*candidate.headline_basis_ids, *candidate.support_basis_ids])),
        unsupported_claim_categories=[],
        compliance_status="approved",
        rejection_reasons=[],
        copy_source_mode="user_exact" if input_evidence.user_exact_display_copy else "generated",
        source_user_request=input_evidence.user_request_utterance or input_evidence.user_text,
        non_display_instructions=input_evidence.non_display_instruction_fragments,
        product_identity=product_understanding.product_name,
        desired_positioning=input_evidence.desired_positioning or product_understanding.desired_positioning,
        campaign_intent=input_evidence.campaign_intent or product_understanding.campaign_intent,
        transformation_performed=True,
        product_evidence_ids=list(candidate.headline_basis_ids or product_understanding.product_name_evidence_ids),
        creative_direction_evidence_ids=[],
        copy_claim_evidence_ids=list(candidate.support_basis_ids),
        selected_candidate_id=candidate.candidate_id,
        positioning_realization_plan=bundle.positioning_plan.model_dump(),
        candidate_scorecard=scorecard.model_dump(),
        alternative_candidate_summaries=[_candidate_summary(item, bundle) for item in bundle.candidates if item.candidate_id != candidate.candidate_id],
        campaign_message_plan=dict(getattr(bundle, "campaign_message_plan", {}) or {}),
        support_basis_type=candidate.support_basis_type,
    )
    failures = validate_approved_native_copy_brief(brief)
    if failures:
        return brief.model_copy(update={"compliance_status": "rejected", "rejection_reasons": failures})
    return brief


def _candidate_summary(candidate, bundle: NativeCopyStrategyBundle) -> dict[str, Any]:
    score = next((item for item in bundle.scorecards if item.candidate_id == candidate.candidate_id), None)
    return {
        "candidate_id": candidate.candidate_id,
        "strategy": candidate.strategy,
        "headline": candidate.headline,
        "supporting_copy": candidate.supporting_copy,
        "blocked": bool(score.blocked) if score else None,
        "total_score": score.total_score if score else None,
        "blocking_reasons": list(score.blocking_reasons) if score else [],
    }


def _coerce_native_copy_payload(
    payload: dict[str, Any],
    *,
    input_evidence: InputEvidenceBundle,
    product_understanding: ProductUnderstanding,
    provider_metadata: dict[str, Any],
) -> dict[str, Any]:
    data = dict(payload or {})
    if data.get("language") == "ko":
        data["language"] = "korean"
    data.setdefault("language", "korean")
    raw_headline = data.get("headline") or data.get("title") or data.get("headline_text") or data.get("consumer_headline") or data.get("display_headline") or data.get("primary_text") or data.get("main_copy")
    raw_support = data.get("supporting_copy") or data.get("support") or data.get("subcopy") or data.get("supporting_text") or data.get("subheadline") or data.get("secondary_text")
    headline = _clean(raw_headline)
    support = _clean(raw_support)
    closing = _clean(data.get("closing_copy") or data.get("closing"))
    action = _clean(data.get("action_cta") or data.get("cta"))
    data["headline"] = headline
    data["supporting_copy"] = support
    data["closing_copy"] = closing if not support else None
    data["action_cta"] = action
    if data.get("message_role") not in {"image_only", "headline_only", "headline_plus_support", "headline_plus_closing"}:
        data["message_role"] = "headline_plus_support" if support else ("headline_plus_closing" if closing else "headline_only")
    texts = [text for text in (headline, support, closing if not support else None) if text]
    data["allowed_texts"] = list(data.get("allowed_texts") or texts)
    data.setdefault("forbidden_texts", [])
    data["max_text_blocks"] = int(data.get("max_text_blocks") or len(texts) or 1)
    data["max_total_characters"] = int(data.get("max_total_characters") or 48)
    product_ids = list(data.get("product_evidence_ids") or product_understanding.product_name_evidence_ids or [])
    direction_ids = list(data.get("creative_direction_evidence_ids") or [])
    if not direction_ids and input_evidence.desired_positioning:
        direction_ids = [item.evidence_id for item in input_evidence.creative_inferences[:2]]
    verified_ids = list(dict.fromkeys([*list(data.get("verified_evidence_ids") or []), *product_ids]))
    data["verified_evidence_ids"] = verified_ids
    data.setdefault("unsupported_claim_categories", [])
    data["compliance_status"] = data.get("compliance_status") or "manual_review"
    data.setdefault("rejection_reasons", [])
    source_mode = str(data.get("copy_source_mode") or "").strip()
    data["copy_source_mode"] = source_mode if source_mode in {"generated", "user_exact"} else ("user_exact" if input_evidence.user_exact_display_copy else "generated")
    data.setdefault("source_user_request", input_evidence.user_request_utterance or input_evidence.user_text)
    data.setdefault("non_display_instructions", input_evidence.non_display_instruction_fragments)
    product_identity = data.get("product_identity")
    if isinstance(product_identity, dict):
        product_identity = product_identity.get("name") or product_identity.get("product_name")
    data["product_identity"] = _clean(product_identity) or product_understanding.product_name
    data.setdefault("desired_positioning", input_evidence.desired_positioning or product_understanding.desired_positioning)
    data.setdefault("campaign_intent", input_evidence.campaign_intent or product_understanding.campaign_intent or input_evidence.user_intent or "product_promotion")
    if not isinstance(data.get("transformation_performed"), bool):
        data["transformation_performed"] = bool(data.get("copy_source_mode") == "user_exact" or (headline and headline != (input_evidence.user_request_utterance or input_evidence.user_text)))
    data.setdefault("product_evidence_ids", product_ids or verified_ids)
    data.setdefault("creative_direction_evidence_ids", direction_ids)
    data.setdefault("copy_claim_evidence_ids", data.get("copy_claim_evidence_ids") or [])
    data["provider_metadata"] = {
        **dict(provider_metadata or {}),
        "raw_headline_present": raw_headline is not None,
        "raw_support_present": raw_support is not None,
        "raw_message_role": payload.get("message_role"),
        "coercion_applied": True,
        "coercion_reasons": _coercion_reasons(payload),
    }
    return data


def _clean(value: Any) -> str | None:
    text = str(value or "").strip()
    return text or None


def _call_openai_native_copy(*, input_evidence: InputEvidenceBundle, product_understanding: ProductUnderstanding, execution_plan: CreativeExecutionPlan) -> dict[str, Any]:
    from openai import OpenAI  # type: ignore

    started = time.perf_counter()
    prompt = (
        "Return JSON only for approved_native_copy_brief_v1. Generate Korean native typography copy for one GPT Image 2 poster. "
        "Use a single top-level JSON object with these keys exactly: headline, supporting_copy, closing_copy, action_cta, language, message_role, allowed_texts, forbidden_texts, max_text_blocks, max_total_characters, verified_evidence_ids, unsupported_claim_categories, compliance_status, rejection_reasons, copy_source_mode, source_user_request, non_display_instructions, product_identity, desired_positioning, campaign_intent, transformation_performed, product_evidence_ids, creative_direction_evidence_ids, copy_claim_evidence_ids. "
        "headline is required unless compliance_status is rejected. "
        "The user's utterance is a request to create an advertisement, not customer-facing display copy. "
        "First separate product identity, desired positioning, campaign intent, exact display copy if explicitly supplied, and non-display instructions. "
        "Unless copy_source_mode=user_exact, do not copy the user's utterance into headline, do not paraphrase the system request as display copy, and do not expose request verbs or campaign instructions. "
        "The headline must speak to the consumer, not describe what the user wants the system to do. "
        "Prohibited meta-instruction leakage: 홍보하고 싶어, 광고해줘, 만들어줘, 소개하고 싶어, I want to promote, create an ad for. "
        "Use requested positioning as creative direction, not as an unverified product claim. "
        "Return product_identity, campaign_intent, desired_positioning, non_display_instructions, copy_source_mode, transformation_performed, product_evidence_ids, creative_direction_evidence_ids, and copy_claim_evidence_ids. "
        "Use only verified evidence and ProductUnderstanding. Max two text blocks. No action CTA unless a verified destination exists; default action_cta null. "
        "No price, discount, date, address, phone, ingredient amount, efficacy, guarantee, generic CTA, or unsupported claim. "
        "Input sections follow. "
        f"USER REQUEST: {input_evidence.user_request_utterance or input_evidence.user_text}\n"
        f"PRODUCT IDENTITY: {product_understanding.product_name}\n"
        f"VERIFIED PRODUCT FACTS: {json.dumps([item.model_dump() for item in input_evidence.explicit_user_facts], ensure_ascii=False)}\n"
        f"CREATIVE DIRECTION: {json.dumps(input_evidence.desired_positioning or product_understanding.desired_positioning, ensure_ascii=False)}\n"
        f"CAMPAIGN INTENT: {input_evidence.campaign_intent or product_understanding.campaign_intent}\n"
        f"NON-DISPLAY INSTRUCTIONS: {json.dumps(input_evidence.non_display_instruction_fragments, ensure_ascii=False)}\n"
        f"USER-APPROVED EXACT DISPLAY COPY: {json.dumps(input_evidence.user_exact_display_copy, ensure_ascii=False)}\n"
        f"UNSUPPORTED CLAIMS: {json.dumps(product_understanding.unsupported_claim_categories, ensure_ascii=False)}\n"
        f"ExecutionPlan: {execution_plan.model_dump_json()} InputEvidenceBundle: {input_evidence.model_dump_json()} ProductUnderstanding: {product_understanding.model_dump_json()}"
    )
    response = OpenAI(timeout=90).responses.create(model="gpt-5.4", input=prompt, temperature=0)
    payload = json.loads(getattr(response, "output_text", "") or "{}")
    payload.setdefault("provider_metadata", {"provider": "openai", "model": "gpt-5.4", "fallback_used": False, "token_usage": _usage_dict(response), "latency_ms": int((time.perf_counter() - started) * 1000)})
    return payload


def _usage_dict(response: Any) -> dict[str, int] | None:
    usage = getattr(response, "usage", None)
    if usage is None:
        return None
    return {
        "input_tokens": int(getattr(usage, "input_tokens", 0) or 0),
        "output_tokens": int(getattr(usage, "output_tokens", 0) or 0),
        "total_tokens": int(getattr(usage, "total_tokens", 0) or 0),
    }


def _coercion_reasons(payload: dict[str, Any]) -> list[str]:
    reasons: list[str] = []
    if not (payload.get("headline") or payload.get("title")):
        reasons.append("headline_missing")
    if not payload.get("compliance_status"):
        reasons.append("compliance_status_missing")
    if payload.get("language") == "ko":
        reasons.append("language_alias_normalized")
    return reasons
