"""GPT-5.4 native copy candidate generation and deterministic ranking."""

from __future__ import annotations

import json
import time
from typing import Any

from openai import OpenAI  # type: ignore

from orchestrator.app.llm.native_copy_policy import SENSORY_LANGUAGE_CUES, build_positioning_realization_plan, direct_positioning_terms_used, score_native_copy_candidate
from orchestrator.app.schemas.input_evidence import InputEvidenceBundle
from orchestrator.app.schemas.native_creative import NativeCopyCandidate, NativeCopyStrategyBundle, ProductExpressionBasis
from orchestrator.app.schemas.product_understanding import ProductUnderstanding


STRATEGIES = ["product_name_first", "sensory_first", "context_first", "minimal_identity"]


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
    return coerce_native_copy_strategy_bundle(payload, input_evidence=input_evidence, product_understanding=product_understanding)


def coerce_native_copy_strategy_bundle(
    payload: dict[str, Any],
    *,
    input_evidence: InputEvidenceBundle,
    product_understanding: ProductUnderstanding,
) -> NativeCopyStrategyBundle:
    product_ids = product_understanding.product_name_evidence_ids or [item.evidence_id for item in input_evidence.explicit_user_facts if item.key == "product_name"]
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
    if len(candidates) < 4:
        candidates.extend(_fallback_candidate_shells(product_understanding.product_name, product_ids, start=len(candidates)))
    if not (basis.permissible_sensory_cues or basis.contextual_cues or basis.visual_cues):
        candidates = [_strip_unsupported_support(candidate) for candidate in candidates]
    scorecards = [
        score_native_copy_candidate(candidate, product_identity=product_understanding.product_name, requested_positioning=plan.requested_positioning, exact_user_copy=bool(input_evidence.user_exact_display_copy))
        for candidate in candidates
    ]
    valid = [score for score in scorecards if not score.blocked]
    recommended = max(valid or scorecards, key=lambda item: item.total_score, default=None)
    return NativeCopyStrategyBundle(
        product_expression_basis=basis,
        positioning_plan=plan,
        candidates=candidates,
        scorecards=scorecards,
        recommended_candidate_id=recommended.candidate_id if recommended and not recommended.blocked else None,
        requires_revision=not bool(recommended and not recommended.blocked),
        revision_reasons=[] if recommended and not recommended.blocked else ["no_unblocked_candidate"],
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
        "Return keys: positioning_plan, candidates. Each candidate needs candidate_id, strategy, headline, supporting_copy, closing_copy, action_cta, headline_basis_ids, support_basis_ids, language, positioning_realization_mode, direct_positioning_terms_used, sensory_terms_used, text_block_count, total_character_count. "
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
    strategy = data.get("strategy") if data.get("strategy") in STRATEGIES else STRATEGIES[min(index, len(STRATEGIES) - 1)]
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
        language=data.get("language") if data.get("language") in {"korean", "english", "mixed"} else "korean",
        positioning_realization_mode=data.get("positioning_realization_mode") if data.get("positioning_realization_mode") in {"implicit", "balanced", "explicit"} else "implicit",
        direct_positioning_terms_used=list(data.get("direct_positioning_terms_used") or direct_positioning_terms_used(" ".join(texts))),
        sensory_terms_used=sensory_terms,
        text_block_count=len([text for text in texts if text]),
        total_character_count=sum(len(text) for text in texts if text),
    )


def _fallback_candidate_shells(product_name: str, product_ids: list[str], *, start: int) -> list[NativeCopyCandidate]:
    output: list[NativeCopyCandidate] = []
    for offset, strategy in enumerate(STRATEGIES[start:]):
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
            "sensory_terms_used": [],
            "text_block_count": 1,
            "total_character_count": len(candidate.headline),
        }
    )
