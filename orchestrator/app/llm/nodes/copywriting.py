"""Rule-based copywriting node for MVP marketing graph."""

from __future__ import annotations

from typing import Any

from orchestrator.app.graph.state import MarketingState, context_to_model
from orchestrator.app.llm.ad_format_policy import role_allowed
from orchestrator.app.llm.copy_quality import apply_copy_quality_policy
from orchestrator.app.llm.copy_tone import get_copy_tone_profile
from orchestrator.app.schemas.llm_marketing import CopywritingOutput, MarketingCopy


def copywriting_node(state: MarketingState) -> dict[str, Any]:
    context = context_to_model(state.get("context"))
    ad_format_spec = state.get("ad_format_spec") or {}
    tone_profile = get_copy_tone_profile(context.business_type, context.target_persona)
    copy = apply_copy_quality_policy(apply_copy_presence_to_copy(build_marketing_copy(context, tone_profile), state.get("copy_presence_plan")))
    output = CopywritingOutput(
        marketing_copy=copy,
        tone_profile=tone_profile,
        rationale="Rule-based v1 copywriting; no LLM call was made.",
    )
    return {
        "marketing_copy": copy.model_dump(),
        "copywriting_output": output.model_dump(),
        "current_brief": {
            **state.get("current_brief", {}),
            "copy_ready": True,
            "copy_ad_format": ad_format_spec.get("ad_format"),
        },
        "status": "copywriting",
    }


def build_marketing_copy(context, tone_profile: dict[str, Any]) -> MarketingCopy:
    item = context.item_or_service or "상품"
    goal = context.promotion_goal or "visit_cta"
    business_type = context.business_type or "store"
    headline = build_headline(item, goal, business_type)
    subcopy = build_subcopy(item, goal, business_type, context.time_context)
    cta = build_cta(goal, context.contact_or_order_method)
    hashtags = build_hashtags(context.business_type, item)
    return MarketingCopy(
        headline=headline,
        subcopy=subcopy,
        cta=cta,
        price_line=context.price_or_discount,
        period_line=context.time_context,
        hashtags=hashtags,
        metadata={
            "tone_voice": tone_profile.get("voice"),
            "hallucination_guard": True,
            "source_node": "copywriting",
        },
    )


def apply_copy_presence_to_copy(copy: MarketingCopy, plan: dict[str, Any] | None) -> MarketingCopy:
    updates: dict[str, Any] = {}
    mode = str((plan or {}).get("mode") or "")
    if not role_allowed("subheadline", plan) or mode in {"brand_only", "headline_only"}:
        updates["subcopy"] = None
    if not role_allowed("cta", plan):
        updates["cta"] = None
    if not role_allowed("price", plan):
        updates["price_line"] = None
    if not role_allowed("disclaimer", plan):
        updates["disclaimer"] = None
    if updates:
        return copy.model_copy(update={**updates, "metadata": {**copy.metadata, "copy_presence_plan_applied": True}})
    return copy


def build_headline(item: str, goal: str, business_type: str) -> str:
    if business_type == "restaurant" and goal == "reservation_cta":
        return f"오늘 회식은 {item}로 결정"
    if goal == "discount_event":
        return f"{item} 혜택을 지금 확인하세요"
    if goal == "new_launch":
        return f"새롭게 만나는 {item}"
    if goal == "review_event":
        return f"{item}, 경험을 남겨보세요"
    return f"{item}이 필요한 순간"


def build_subcopy(item: str, goal: str, business_type: str, time_context: str | None) -> str:
    prefix = f"{time_context}에 " if time_context else ""
    if business_type == "restaurant":
        return f"{prefix}두툼하게 준비한 {item}과 편안한 자리, 지금 확인해보세요."
    if business_type == "cafe":
        return f"{prefix}{item} 한 잔으로 잠깐의 여유를 더해보세요."
    if business_type == "fitness":
        return f"{prefix}{item}로 오늘의 루틴을 시작해보세요."
    if goal == "new_launch":
        return f"{prefix}새롭게 준비한 {item}을 만나보세요."
    return f"{prefix}{item}의 장점을 간결하게 담은 안내입니다."


def build_cta(goal: str, contact_or_order_method: str | None) -> str:
    if contact_or_order_method:
        return f"{contact_or_order_method}로 문의하기"
    if goal == "reservation_cta":
        return "예약 문의하기"
    if goal == "discount_event":
        return "혜택 확인하기"
    if goal == "review_event":
        return "리뷰 참여하기"
    return "지금 확인하기"


def build_hashtags(business_type: str | None, item: str) -> list[str]:
    tags = [f"#{item.replace(' ', '')}"]
    if business_type:
        tags.append(f"#{business_type}")
    return tags[:3]
