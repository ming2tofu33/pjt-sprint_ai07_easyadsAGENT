"""Prompt builders for grounded copy generation."""

from __future__ import annotations

from orchestrator.app.llm.copy_grounding import BUSINESS_DOMAIN, DOMAIN_TERMS, build_context_anchors, find_wrong_domain_terms
from orchestrator.app.schemas.llm_marketing import CopyMessageStrategy, MarketingContext
from orchestrator.app.schemas.text_layout import CopyVisualIntent


def build_copy_generation_v2_prompt(
    *,
    context: MarketingContext,
    strategy: CopyMessageStrategy,
    visual_intent: CopyVisualIntent | None = None,
) -> str:
    anchors = build_context_anchors(context, strategy)
    expected_domain = BUSINESS_DOMAIN.get(str(context.business_type or "").lower())
    wrong_terms = []
    if expected_domain:
        for domain, terms in DOMAIN_TERMS.items():
            if domain != expected_domain:
                wrong_terms.extend(terms[:8])
    intent_text = visual_intent.model_dump() if visual_intent else {}
    return "\n".join(
        [
            "You are generating Korean advertising copy for the exact business context below.",
            "Return strict JSON only: {\"candidates\":[{\"id\":\"copy_1\",\"headline\":\"...\",\"subcopy\":\"...\",\"cta\":\"...\",\"angle\":\"product_first\",\"strategy_summary\":\"...\",\"metadata\":{}}],\"recommended_candidate_id\":\"copy_1\",\"metadata\":{}}.",
            "Generate exactly three candidates with angles product_first, emotion_first, benefit_action_first.",
            "Every headline or subcopy must directly mention the current product/service or a close domain anchor.",
            "Do not invent unrelated products, electronics, phones, watches, AI devices, cameras, video, chips, batteries, education, or health devices unless the context explicitly says so.",
            f"business_type: {context.business_type}",
            f"item_or_service: {context.item_or_service}",
            f"promotion_goal: {context.promotion_goal}",
            f"brand_tone: {context.brand_tone}",
            f"target_customer: {context.target_persona}",
            f"known_facts: {context.model_dump()}",
            f"supported_facts: {strategy.supported_facts or strategy.product_truths or anchors}",
            f"forbidden_claims: {strategy.forbidden_claims}",
            f"primary_value: {strategy.primary_value}",
            f"customer_desire: {strategy.customer_desire}",
            f"emotional_hook: {strategy.emotional_hook}",
            f"proof_or_detail: {strategy.proof_or_detail}",
            f"CTA intent: {strategy.cta_intent or strategy.conversion_goal}",
            f"required_domain_anchors: {anchors}",
            f"wrong_domain_examples_to_avoid: {sorted(set(wrong_terms))}",
            f"copy_visual_intent: {intent_text}",
            "If a CTA is not required, keep cta short and non-button-like, or empty only when allowed by visual intent.",
            "Reject generic emotional copy that could fit any product.",
        ]
    )


def copy_has_wrong_domain_terms(text: str, context: MarketingContext) -> bool:
    return bool(find_wrong_domain_terms(text.lower(), context.business_type))
