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
    goal_description = _promotion_goal_description(context.promotion_goal)
    public_facts = {
        "business_category": _business_description(context.business_type),
        "product_or_service": context.item_or_service,
        "brand_tone": context.brand_tone,
        "target_customer": context.target_persona,
        "goal": goal_description,
    }
    return "\n".join(
        [
            "You are generating Korean advertising copy for the exact business context below.",
            "Return strict JSON only: {\"candidates\":[{\"id\":\"copy_1\",\"headline\":\"...\",\"subcopy\":\"...\",\"cta\":\"...\",\"angle\":\"product_first\",\"strategy_summary\":\"...\",\"metadata\":{}}],\"recommended_candidate_id\":\"copy_1\",\"metadata\":{}}.",
            "Generate exactly three candidates with angles product_first, emotion_first, benefit_action_first.",
            "Every headline or subcopy must directly mention the current product/service or a close domain anchor.",
            "Do not output internal enum names, snake_case identifiers, candidate ids, or strategy labels.",
            "Do not invent unrelated products, electronics, phones, watches, AI devices, cameras, video, chips, batteries, education, or health devices unless the context explicitly says so.",
            f"public_safe_facts: {public_facts}",
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
            "For menu exploration goals, do not write consultation, inquiry, booking, or application CTAs.",
            "For macaron collection ads, do not mention meat, barbecue, meals, beverages, devices, or service consultation.",
            "Reject generic emotional copy that could fit any product.",
        ]
    )


def copy_has_wrong_domain_terms(text: str, context: MarketingContext) -> bool:
    return bool(find_wrong_domain_terms(text.lower(), context.business_type))


def _promotion_goal_description(goal: str | None) -> str:
    return {
        "menu_discovery": "여러 메뉴와 맛 구성을 둘러보도록 유도",
        "reservation_cta": "방문 또는 예약 행동 유도",
        "consultation": "상담 요청 유도",
        "brand_awareness": "브랜드 분위기 인지",
    }.get(str(goal or ""), "상품 또는 서비스를 자연스럽게 살펴보도록 유도")


def _business_description(business_type: str | None) -> str:
    return {
        "macaron": "마카롱 디저트",
        "restaurant_bbq": "숯불구이 음식점",
        "beauty_nail": "네일 뷰티",
    }.get(str(business_type or ""), str(business_type or "local business"))
