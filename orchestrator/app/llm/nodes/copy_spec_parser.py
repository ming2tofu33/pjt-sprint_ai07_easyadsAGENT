"""Convert MarketingCopy into TLFP CopySpec."""

from __future__ import annotations

from typing import Any

from orchestrator.app.llm.metadata_builders import build_copy_spec_parser_metadata, build_metadata_contract_summary
from orchestrator.app.llm.copy_visual_intent import resolve_copy_visual_intent
from orchestrator.app.graph.state import context_to_model, read_model, write_model
from orchestrator.app.schemas.llm_marketing import MarketingCopy
from orchestrator.app.schemas.text_layout import CopyItem, CopySpec, CopyVisualIntent


def copy_spec_parser_node(state: dict[str, Any]) -> dict[str, Any]:
    metadata_contract = build_copy_spec_parser_metadata(state)
    metadata_summary = build_metadata_contract_summary(metadata_contract)
    if state.get("copy_generation_mode") == "no_copy" or state.get("copy_required") is False:
        copy_spec = build_no_copy_spec(metadata_summary)
        return {
            "copy_spec": write_model(copy_spec),
            "current_brief": {**state.get("current_brief", {}), "copy_spec_ready": True},
            "status": "bypassing_copy",
        }
    marketing_copy = read_model(state, "marketing_copy", MarketingCopy)
    context = context_to_model(state.get("context"))
    intent = read_model(state, "copy_visual_intent", CopyVisualIntent, default=None) or resolve_copy_visual_intent(context, selected_reference_template=state.get("selected_reference_template"))
    items: list[CopyItem] = [
        CopyItem(role="headline", text=marketing_copy.headline, priority=1),
    ]
    if marketing_copy.subcopy and intent.body_density != "none":
        items.append(CopyItem(role="subheadline", text=marketing_copy.subcopy, priority=3))
    if marketing_copy.price_line or context.price_or_discount:
        items.append(CopyItem(role="price", text=marketing_copy.price_line or context.price_or_discount or "", priority=2))
    ad_format = state.get("ad_format") or state.get("current_brief", {}).get("requested_ad_format") or ""
    if ad_format in ("poster", "flyer", "banner", "product_detail"):
        intent.cta_visibility = "hidden"

    if marketing_copy.cta and intent.cta_visibility != "hidden" and intent.cta_style != "none":
        items.append(CopyItem(role="cta", text=marketing_copy.cta, priority=4))
    if marketing_copy.disclaimer:
        items.append(CopyItem(role="disclaimer", text=marketing_copy.disclaimer, priority=8))

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
        },
    )
    return {
        "copy_spec": write_model(copy_spec),
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
