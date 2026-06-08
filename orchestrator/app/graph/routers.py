"""Conditional routers for the LLM/LangGraph intake mini graph."""

from __future__ import annotations

from langgraph.graph import END

from orchestrator.app.graph.state import MarketingState


def route_by_entry_mode(state: MarketingState) -> str:
    return "validator"


def route_after_input_assets(state: MarketingState) -> str:
    if state.get("source_image_path"):
        return "product_preprocess"
    if state.get("reference_image_path"):
        return "reference_preprocess"
    return "validator"


def route_after_input_reference_template(state: MarketingState) -> str:
    if state.get("selected_reference_template_id"):
        return "reference_template_resolve"
    return route_after_input_assets(state)


def route_after_reference_template_resolve(state: MarketingState) -> str:
    return route_after_input_assets(state)


def route_after_product_preprocess(state: MarketingState) -> str:
    if state.get("reference_image_path") and not state.get("reference_style_profile"):
        return "reference_preprocess"
    return "validator"


def route_after_validator_for_intake(state: MarketingState) -> str:
    if state.get("missing_fields"):
        return "options"
    return END


def route_after_validator_for_marketing(state: MarketingState) -> str:
    if state.get("missing_fields"):
        return "options"
    return "format_planner"


def route_after_tone_binding(state: MarketingState) -> str:
    mode = state.get("copy_generation_mode")
    if mode == "suggest_candidates":
        return "copy_candidate_generation"
    if mode == "custom_input":
        return "custom_copy_input"
    if mode == "no_copy":
        return "no_copy_bypass"
    return "auto_pilot_copywriting"


def route_by_copy_presence(state: MarketingState) -> str:
    copy_spec = state.get("copy_spec") or {}
    if (
        state.get("copy_required") is False
        or state.get("text_overlay_pending") is False
        or state.get("copy_generation_mode") == "no_copy"
        or copy_spec.get("copy_mode") == "no_copy"
    ):
        return "result"
    return "text_renderer"


def route_after_t2i_generation(state: MarketingState) -> str:
    status = state.get("status")
    if status in {"modal_running", "failed"}:
        return END
    return "background_validation"


route_after_validator = route_after_validator_for_intake
