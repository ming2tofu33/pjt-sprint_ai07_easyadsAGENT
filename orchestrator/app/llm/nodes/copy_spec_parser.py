"""Convert MarketingCopy into TLFP CopySpec."""

from __future__ import annotations

from typing import Any

from orchestrator.app.llm.ad_format_policy import role_allowed
from orchestrator.app.llm.metadata_builders import build_copy_spec_parser_metadata, build_metadata_contract_summary
from orchestrator.app.llm.copy_visual_intent import resolve_copy_visual_intent
from orchestrator.app.schemas.llm_marketing import MarketingContext, MarketingCopy
from orchestrator.app.schemas.text_layout import CopyItem, CopySpec, CopyVisualIntent


def copy_spec_parser_node(state: dict[str, Any]) -> dict[str, Any]:
    metadata_contract = build_copy_spec_parser_metadata(state)
    metadata_summary = build_metadata_contract_summary(metadata_contract)
    if state.get("copy_generation_mode") == "no_copy" or state.get("copy_required") is False:
        copy_spec = build_no_copy_spec(metadata_summary)
        return {
            "copy_spec": copy_spec.model_dump(),
            "current_brief": {**state.get("current_brief", {}), "copy_spec_ready": True},
            "status": "bypassing_copy",
        }
    marketing_copy = MarketingCopy(**(state.get("marketing_copy") or {}))
    context = _context_to_model(state.get("context"))
    intent = CopyVisualIntent(**(state.get("copy_visual_intent") or resolve_copy_visual_intent(context, selected_reference_template=state.get("selected_reference_template")).model_dump()))
    items: list[CopyItem] = [
        CopyItem(role="headline", text=marketing_copy.headline, priority=1),
    ]
    if marketing_copy.subcopy and intent.body_density != "none" and role_allowed("subheadline", state.get("copy_presence_plan")):
        items.append(CopyItem(role="subheadline", text=marketing_copy.subcopy, priority=3))
    if (marketing_copy.price_line or context.price_or_discount) and role_allowed("price", state.get("copy_presence_plan")):
        items.append(CopyItem(role="price", text=marketing_copy.price_line or context.price_or_discount or "", priority=2))
    verified = _verified_information(state, context)
    if verified.get("discount") and role_allowed("discount", state.get("copy_presence_plan")):
        items.append(CopyItem(role="discount", text=str(verified["discount"]), priority=2))
    if verified.get("period") and role_allowed("period", state.get("copy_presence_plan")):
        items.append(CopyItem(role="period", text=str(verified["period"]), priority=3))
    if verified.get("benefits") and role_allowed("body", state.get("copy_presence_plan")):
        items.append(CopyItem(role="body", text=" · ".join(str(item) for item in verified["benefits"]), priority=4))
    if verified.get("proof") and role_allowed("badge", state.get("copy_presence_plan")):
        items.append(CopyItem(role="badge", text=str(verified["proof"]), priority=5))
    store_info = verified.get("store_info")
    if store_info and role_allowed("store_info", state.get("copy_presence_plan")):
        items.append(CopyItem(role="store_info", text=str(store_info), priority=6))
    if marketing_copy.cta and intent.cta_visibility != "hidden" and intent.cta_style != "none" and role_allowed("cta", state.get("copy_presence_plan")):
        items.append(CopyItem(role="cta", text=marketing_copy.cta, priority=4))
    if marketing_copy.disclaimer and role_allowed("disclaimer", state.get("copy_presence_plan")):
        items.append(CopyItem(role="disclaimer", text=marketing_copy.disclaimer, priority=8))
    items = [item for item in items if role_allowed(item.role, state.get("copy_presence_plan"))]

    copy_spec = CopySpec(
        items=items,
        copy_mode=str(marketing_copy.metadata.get("copy_mode") or "standard"),
        tone_profile={
            "tone_voice": marketing_copy.metadata.get("tone_voice"),
            "business_type": context.business_type,
            "promotion_goal": context.promotion_goal,
        },
        metadata={
            "source_node": "copy_spec_parser",
            "no_new_facts": True,
            "llm_metadata_summary": metadata_summary,
            "copy_visual_intent": intent.model_dump(),
            "copy_presence_plan": state.get("copy_presence_plan"),
            "ad_format_contract": state.get("ad_format_contract"),
        },
    )
    return {
        "copy_spec": copy_spec.model_dump(),
        "current_brief": {**state.get("current_brief", {}), "copy_spec_ready": True},
        "status": "copywriting",
    }


def build_no_copy_spec(metadata_summary: dict[str, Any] | None = None) -> CopySpec:
    return CopySpec(
        items=[],
        copy_mode="no_copy",
        tone_profile={},
        metadata={
            "source_node": "copy_spec_parser",
            "no_new_facts": True,
            "llm_metadata_summary": metadata_summary or {},
        },
    )


def _context_to_model(context: dict[str, Any] | MarketingContext | None) -> MarketingContext:
    if isinstance(context, MarketingContext):
        return context
    if isinstance(context, dict):
        return MarketingContext(**context)
    return MarketingContext()


def _verified_information(state: dict[str, Any], context: MarketingContext) -> dict[str, Any]:
    extra = context.extra or {}
    required = state.get("required_information") if isinstance(state.get("required_information"), dict) else {}
    return {
        "discount": required.get("discount") or extra.get("discount") or context.price_or_discount,
        "period": required.get("period") or extra.get("period") or context.time_context,
        "benefits": required.get("benefits") or extra.get("benefits") or [],
        "proof": required.get("proof") or extra.get("proof"),
        "store_info": required.get("store_info") or extra.get("store_info") or context.location_text or context.contact_or_order_method,
    }
