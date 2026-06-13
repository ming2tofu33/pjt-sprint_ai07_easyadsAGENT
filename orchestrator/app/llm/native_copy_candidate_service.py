"""GPT-5.4 native copy candidate generation and deterministic ranking."""

from __future__ import annotations

import json
import time
from typing import Any

from openai import OpenAI  # type: ignore

from orchestrator.app.llm.native_copy_policy import SENSORY_LANGUAGE_CUES, build_positioning_realization_plan, direct_positioning_terms_used, score_native_copy_candidate
from orchestrator.app.schemas.input_evidence import InputEvidenceBundle
from orchestrator.app.schemas.native_creative import CampaignMessagePlan, NativeCopyCandidate, NativeCopyStrategyBundle, ProductExpressionBasis
from orchestrator.app.schemas.product_understanding import ProductUnderstanding


STRATEGIES = ["minimal_identity", "product_detail", "sensory_expression", "campaign_context", "brand_editorial"]


def generate_native_copy_strategy_bundle(
    *,
    input_evidence: InputEvidenceBundle,
    product_understanding: ProductUnderstanding,
    source_visual_analysis: dict | None,
    state: dict[str, Any],
) -> NativeCopyStrategyBundle:
    adapter = state.get("native_copy_candidate_adapter")
    if adapter:
        payload = adapter.generate_native_copy_strategy_bundle(input_evidence=input_evidence, product_understanding=product_understanding, source_visual_analysis=source_visual_analysis, state=state)
    else:
        payload = _call_openai_candidates(input_evidence=input_evidence, product_understanding=product_understanding, source_visual_analysis=source_visual_analysis)
    if state.get("campaign_message_plan") and not payload.get("campaign_message_plan"):
        payload = {**payload, "campaign_message_plan": state["campaign_message_plan"]}
    return coerce_native_copy_strategy_bundle(payload, input_evidence=input_evidence, product_understanding=product_understanding)


def coerce_native_copy_strategy_bundle(
    payload: dict[str, Any],
    *,
    input_evidence: InputEvidenceBundle,
    product_understanding: ProductUnderstanding,
) -> NativeCopyStrategyBundle:
    product_ids = product_understanding.product_name_evidence_ids or [item.evidence_id for item in input_evidence.explicit_user_facts if item.key == "product_name"]
    campaign_plan_payload = payload.get("campaign_message_plan") or {}
    campaign_plan = CampaignMessagePlan(**campaign_plan_payload) if campaign_plan_payload else None
    basis = ProductExpressionBasis(
        product_identity=product_understanding.product_name,
        verified_product_cues=list(product_understanding.verified_facts or input_evidence.explicit_user_facts),
        permissible_sensory_cues=list(product_understanding.permissible_inferences),
        contextual_cues=[item for item in input_evidence.explicit_user_facts if item.key in {"business_context", "launch_status"}],
        visual_cues=list(product_understanding.visual_observations or input_evidence.visual_observations),
        unsupported_cues=list(product_understanding.unsupported_claim_categories),
        unknown_cues=list(product_understanding.unknown_fields),
        selected_headline_basis_ids=list(product_ids),
        selected_support_basis_ids=[],
    )
    plan_payload = payload.get("positioning_plan") or payload.get("positioning_realization_plan") or {}
    plan = build_positioning_realization_plan(
        requested_positioning=list(plan_payload.get("requested_positioning") or input_evidence.desired_positioning or product_understanding.desired_positioning),
        exact_user_copy=bool(input_evidence.user_exact_display_copy),
    )
    raw_candidates = payload.get("candidates") or payload.get("native_copy_candidates") or []
    candidates = [_coerce_candidate(item, index=i, product_name=product_understanding.product_name, product_ids=product_ids) for i, item in enumerate(raw_candidates[:4])]
    candidates = [item for item in candidates if item.headline]
    capacity = _candidate_capacity(campaign_plan=campaign_plan, basis=basis)
    requested_count = 4
    if capacity != "single_minimal" and len(candidates) < requested_count:
        candidates.extend(_fallback_candidate_shells(product_understanding.product_name, product_ids, start=len(candidates), limit=requested_count))
    if not _support_allowed(campaign_plan=campaign_plan, basis=basis):
        candidates = [_strip_unsupported_support(candidate) for candidate in candidates]
    elif campaign_plan and campaign_plan.support_function in {"launch_context", "brand_mood", "usage_context"}:
        candidates = [_apply_campaign_support_basis(candidate, product_ids=product_ids, campaign_plan=campaign_plan) for candidate in candidates]
    candidates, dedupe_reasons = _dedupe_candidates(candidates)
    if capacity == "single_minimal":
        candidates = candidates[:1]
    elif capacity == "limited":
        candidates = candidates[:3]
    scorecards = [
        score_native_copy_candidate(
            candidate,
            product_identity=product_understanding.product_name,
            requested_positioning=plan.requested_positioning,
            exact_user_copy=bool(input_evidence.user_exact_display_copy),
            campaign_message_plan=campaign_plan.model_dump() if campaign_plan else None,
        )
        for candidate in candidates
    ]
    valid = [score for score in scorecards if not score.blocked]
    recommended = max(valid or scorecards, key=lambda item: item.total_score, default=None)
    return NativeCopyStrategyBundle(
        product_expression_basis=basis,
        positioning_plan=plan,
        campaign_message_plan=campaign_plan.model_dump() if campaign_plan else {},
        candidates=candidates,
        scorecards=scorecards,
        recommended_candidate_id=recommended.candidate_id if recommended and not recommended.blocked else None,
        requires_revision=not bool(recommended and not recommended.blocked),
        revision_reasons=[] if recommended and not recommended.blocked else ["no_unblocked_candidate"],
        requested_candidate_count=requested_count,
        generated_candidate_count=len(raw_candidates),
        effective_candidate_count=len(candidates),
        candidate_capacity=capacity,
        diversity_constraints=_diversity_constraints(campaign_plan=campaign_plan, basis=basis),
        deduplication_reasons=dedupe_reasons,
    )


def _call_openai_candidates(*, input_evidence: InputEvidenceBundle, product_understanding: ProductUnderstanding, source_visual_analysis: dict | None) -> dict[str, Any]:
    started = time.perf_counter()
    prompt = (
        "Return JSON only for NativeCopyStrategyBundle candidate generation. Generate exactly 4 Korean native typography copy candidates. "
        "The user's desired positioning is not automatically display copy. Do not simply translate positioning adjectives into headline claims. "
        "Weak literalization examples: premium->프리미엄, refined->품격 있게, elegant->우아하게, luxury->럭셔리한. "
        "The final copy should primarily express product identity, safely inferable experience, and use context. "
        "A premium/refined impression may be carried by restrained wording, typography, spacing, composition, color, lighting, material and texture. "
        "Prefer product-centered concrete language over self-congratulatory status language. The headline may be only the product name. "
        "Supporting copy must add a different dimension from the headline; if it does not add information, use null. "
        "Return keys: positioning_plan, candidates. Each candidate needs candidate_id, strategy, headline, supporting_copy, closing_copy, action_cta, headline_basis_ids, support_basis_ids, support_basis_type, language, positioning_realization_mode, direct_positioning_terms_used, sensory_terms_used, text_block_count, total_character_count. "
        f"USER REQUEST: {input_evidence.user_request_utterance or input_evidence.user_text}\n"
        f"PRODUCT IDENTITY: {product_understanding.product_name}\n"
        f"VERIFIED PRODUCT FACTS: {json.dumps([item.model_dump() for item in input_evidence.explicit_user_facts], ensure_ascii=False)}\n"
        f"PERMISSIBLE PRODUCT INFERENCES: {json.dumps([item.model_dump() for item in product_understanding.permissible_inferences], ensure_ascii=False)}\n"
        f"VISUAL OBSERVATIONS: {json.dumps([item.model_dump() for item in input_evidence.visual_observations], ensure_ascii=False)}\n"
        f"DESIRED POSITIONING: {json.dumps(input_evidence.desired_positioning or product_understanding.desired_positioning, ensure_ascii=False)}\n"
        f"CAMPAIGN INTENT: {input_evidence.campaign_intent or product_understanding.campaign_intent}\n"
        f"NON-DISPLAY INSTRUCTIONS: {json.dumps(input_evidence.non_display_instruction_fragments, ensure_ascii=False)}\n"
        f"EXACT USER COPY: {json.dumps(input_evidence.user_exact_display_copy, ensure_ascii=False)}\n"
        f"UNSUPPORTED CLAIMS: {json.dumps(product_understanding.unsupported_claim_categories, ensure_ascii=False)}"
    )
    response = OpenAI(timeout=90).responses.create(model="gpt-5.4", input=prompt, temperature=0)
    payload = json.loads(getattr(response, "output_text", "") or "{}")
    payload.setdefault("provider_metadata", {"provider": "openai", "model": "gpt-5.4", "latency_ms": int((time.perf_counter() - started) * 1000)})
    return payload


def _coerce_candidate(payload: dict[str, Any], *, index: int, product_name: str, product_ids: list[str]) -> NativeCopyCandidate:
    data = dict(payload or {})
    headline = str(data.get("headline") or "").strip()
    support = str(data.get("supporting_copy") or data.get("support") or data.get("subcopy") or "").strip() or None
    closing = str(data.get("closing_copy") or "").strip() or None
    strategy = _normalize_strategy(data.get("strategy"), index)
    texts = [headline, support or closing or ""]
    sensory_terms = list(data.get("sensory_terms_used") or _sensory_terms_used(" ".join(texts)))
    return NativeCopyCandidate(
        candidate_id=str(data.get("candidate_id") or f"candidate_{index + 1}"),
        strategy=strategy,  # type: ignore[arg-type]
        headline=headline or product_name,
        supporting_copy=support,
        closing_copy=closing if not support else None,
        action_cta=None,
        headline_basis_ids=list(data.get("headline_basis_ids") or product_ids),
        support_basis_ids=list(data.get("support_basis_ids") or []),
        support_basis_type=data.get("support_basis_type") if data.get("support_basis_type") in {"none", "verified_fact", "permissible_sensory_inference", "campaign_context", "aesthetic_expression"} else ("campaign_context" if strategy == "campaign_context" and support else "none"),
        language=data.get("language") if data.get("language") in {"korean", "english", "mixed"} else "korean",
        positioning_realization_mode=data.get("positioning_realization_mode") if data.get("positioning_realization_mode") in {"implicit", "balanced", "explicit"} else "implicit",
        direct_positioning_terms_used=list(data.get("direct_positioning_terms_used") or direct_positioning_terms_used(" ".join(texts))),
        sensory_terms_used=sensory_terms,
        text_block_count=len([text for text in texts if text]),
        total_character_count=sum(len(text) for text in texts if text),
    )


def _fallback_candidate_shells(product_name: str, product_ids: list[str], *, start: int, limit: int) -> list[NativeCopyCandidate]:
    output: list[NativeCopyCandidate] = []
    for offset, strategy in enumerate(STRATEGIES[start:limit]):
        cid = f"candidate_{start + offset + 1}"
        output.append(
            NativeCopyCandidate(
                candidate_id=cid,
                strategy=strategy,  # type: ignore[arg-type]
                headline=product_name,
                supporting_copy=None,
                headline_basis_ids=list(product_ids),
                support_basis_ids=[],
                language="korean",
                positioning_realization_mode="implicit",
                direct_positioning_terms_used=[],
                sensory_terms_used=[],
                text_block_count=1,
                total_character_count=len(product_name),
            )
        )
    return output


def _sensory_terms_used(text: str) -> list[str]:
    lowered = text.lower()
    return sorted(cue for cue in SENSORY_LANGUAGE_CUES if cue.lower() in lowered)


def _strip_unsupported_support(candidate: NativeCopyCandidate) -> NativeCopyCandidate:
    return candidate.model_copy(
        update={
            "supporting_copy": None,
            "closing_copy": None,
            "support_basis_ids": [],
            "support_basis_type": "none",
            "sensory_terms_used": [],
            "text_block_count": 1,
            "total_character_count": len(candidate.headline),
        }
    )


def _apply_campaign_support_basis(candidate: NativeCopyCandidate, *, product_ids: list[str], campaign_plan: CampaignMessagePlan) -> NativeCopyCandidate:
    if not (candidate.supporting_copy or candidate.closing_copy):
        return candidate
    support = candidate.supporting_copy
    if campaign_plan.campaign_role == "new_product_introduction":
        support = "새롭게 선보이는 메뉴입니다"
    return candidate.model_copy(
        update={
            "supporting_copy": support,
            "closing_copy": None,
            "support_basis_type": "campaign_context" if candidate.support_basis_type == "none" else candidate.support_basis_type,
            "support_basis_ids": candidate.support_basis_ids or list(product_ids),
            "text_block_count": 2,
            "total_character_count": len(candidate.headline) + len(support or ""),
        }
    )


def normalize_copy(value: str | None) -> str:
    return "".join(ch.lower() for ch in (value or "") if ch.isalnum())


def candidate_semantic_key(candidate: NativeCopyCandidate) -> tuple[str, str, str]:
    return (normalize_copy(candidate.headline), normalize_copy(candidate.supporting_copy or ""), normalize_copy(candidate.closing_copy or ""))


def _dedupe_candidates(candidates: list[NativeCopyCandidate]) -> tuple[list[NativeCopyCandidate], list[str]]:
    unique: list[NativeCopyCandidate] = []
    reasons: list[str] = []
    seen: set[tuple[str, str, str]] = set()
    for candidate in candidates:
        key = candidate_semantic_key(candidate)
        if key in seen or any(_similarity(key[0], candidate_semantic_key(item)[0]) >= 0.9 and _similarity(key[1], candidate_semantic_key(item)[1]) >= 0.9 for item in unique):
            reasons.append(f"duplicate_removed:{candidate.candidate_id}")
            continue
        seen.add(key)
        unique.append(candidate)
    return unique, reasons


def _similarity(left: str, right: str) -> float:
    if not left and not right:
        return 1.0
    if not left or not right:
        return 0.0
    overlap = len(set(left) & set(right))
    return overlap / max(len(set(left)), len(set(right)))


def _candidate_capacity(*, campaign_plan: CampaignMessagePlan | None, basis: ProductExpressionBasis) -> str:
    if not _support_allowed(campaign_plan=campaign_plan, basis=basis):
        return "single_minimal"
    if campaign_plan and campaign_plan.campaign_role in {"new_product_introduction", "brand_editorial"}:
        return "limited"
    return "full"


def _support_allowed(*, campaign_plan: CampaignMessagePlan | None, basis: ProductExpressionBasis) -> bool:
    if campaign_plan and campaign_plan.visible_copy_mode == "headline_plus_support":
        return True
    return bool(basis.permissible_sensory_cues or basis.contextual_cues or basis.visual_cues)


def _diversity_constraints(*, campaign_plan: CampaignMessagePlan | None, basis: ProductExpressionBasis) -> list[str]:
    constraints = ["dedupe_by_normalized_visible_copy", "do_not_fill_shell_candidates"]
    if campaign_plan:
        constraints.append(f"campaign_role:{campaign_plan.campaign_role}")
        constraints.append(f"visible_copy_mode:{campaign_plan.visible_copy_mode}")
    if not _support_allowed(campaign_plan=campaign_plan, basis=basis):
        constraints.append("support_disallowed_without_basis")
    return constraints


def _normalize_strategy(value: Any, index: int) -> str:
    aliases = {
        "product_name_first": "minimal_identity",
        "sensory_first": "sensory_expression",
        "context_first": "campaign_context",
        "product_attribute_first": "product_detail",
    }
    raw = str(value or "")
    mapped = aliases.get(raw, raw)
    return mapped if mapped in STRATEGIES else STRATEGIES[min(index, len(STRATEGIES) - 1)]
