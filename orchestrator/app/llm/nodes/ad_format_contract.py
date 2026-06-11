"""Ad format and copy presence planning nodes."""

from __future__ import annotations

from typing import Any

from orchestrator.app.llm.ad_format_policy import (
    build_ad_format_contract,
    build_copy_presence_plan,
    build_information_panel_plan,
    decide_creative_lane,
)
from orchestrator.app.schemas.ad_format import AdFormatContract, CopyPresencePlan, CreativeLaneDecision


def ad_format_contract_node(state: dict[str, Any]) -> dict[str, Any]:
    contract = build_ad_format_contract(state)
    return {
        "ad_format_contract": contract.model_dump(),
        "platform_safe_zone_spec": contract.platform_safe_zones.model_dump(),
        "current_brief": {
            **state.get("current_brief", {}),
            "placement": contract.placement,
            "interaction_mode": contract.interaction_mode,
            "embedded_cta_policy": contract.embedded_cta_policy,
        },
        "status": "planning_ad_format_contract",
    }


def creative_lane_decision_node(state: dict[str, Any]) -> dict[str, Any]:
    contract = AdFormatContract(**(state.get("ad_format_contract") or build_ad_format_contract(state).model_dump()))
    decision = decide_creative_lane(state, contract)
    return {
        "creative_lane_decision": decision.model_dump(),
        "current_brief": {**state.get("current_brief", {}), "creative_lane": decision.lane, "creative_archetype": decision.archetype},
        "status": "deciding_creative_lane",
    }


def copy_presence_planner_node(state: dict[str, Any]) -> dict[str, Any]:
    contract = AdFormatContract(**(state.get("ad_format_contract") or build_ad_format_contract(state).model_dump()))
    lane = CreativeLaneDecision(**(state.get("creative_lane_decision") or decide_creative_lane(state, contract).model_dump()))
    plan = build_copy_presence_plan(contract, lane, state)
    updates: dict[str, Any] = {
        "copy_presence_plan": plan.model_dump(),
        "current_brief": {**state.get("current_brief", {}), "copy_presence_mode": plan.mode},
        "status": "planning_copy_presence",
    }
    if plan.mode == "image_only":
        updates.update({"copy_generation_mode": "no_copy", "copy_required": False, "text_overlay_pending": False})
    else:
        updates.update({"copy_required": True, "text_overlay_pending": True})
    return updates


def information_panel_planner_node(state: dict[str, Any]) -> dict[str, Any]:
    contract = AdFormatContract(**(state.get("ad_format_contract") or build_ad_format_contract(state).model_dump()))
    lane = CreativeLaneDecision(**(state.get("creative_lane_decision") or decide_creative_lane(state, contract).model_dump()))
    panel = build_information_panel_plan(contract, lane)
    plan = CopyPresencePlan(**(state.get("copy_presence_plan") or build_copy_presence_plan(contract, lane, state).model_dump()))
    return {
        "information_panel_plan": panel.model_dump(),
        "current_brief": {
            **state.get("current_brief", {}),
            "information_panel_enabled": panel.enabled,
            "information_panel_type": panel.panel_type,
            "max_text_area_ratio": plan.max_text_area_ratio,
        },
        "status": "planning_information_panel",
    }
