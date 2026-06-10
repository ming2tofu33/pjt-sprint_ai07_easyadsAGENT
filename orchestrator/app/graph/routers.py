"""Conditional routers for the LLM/LangGraph intake mini graph."""

from __future__ import annotations

from langgraph.graph import END

from orchestrator.app.graph.state import MarketingState
from orchestrator.app.ocr_gate import settings as ocr_settings


def route_by_entry_mode(state: MarketingState) -> str:
    return "validator"


def route_after_input_assets(state: MarketingState) -> str:
    if state.get("source_asset_id") or state.get("source_image_path"):
        return "product_preprocess"
    if state.get("reference_asset_id") or state.get("reference_image_path"):
        return "reference_preprocess"
    return "validator"


def route_after_input_reference_template(state: MarketingState) -> str:
    if state.get("selected_reference_template_id"):
        return "reference_template_resolve"
    return route_after_input_assets(state)


def route_after_reference_template_resolve(state: MarketingState) -> str:
    return route_after_input_assets(state)


def route_after_product_preprocess(state: MarketingState) -> str:
    if (state.get("reference_asset_id") or state.get("reference_image_path")) and not state.get("reference_style_profile"):
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
        if state.get("selected_copy_id") and state.get("copy_candidates"):
            return "state_update_selected_copy"
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


def route_after_layout_refiner(state: MarketingState) -> str:
    refinement = state.get("layout_refinement_result") or {}
    action = refinement.get("action") if isinstance(refinement, dict) else None
    attempts = int(state.get("layout_revision_attempts") or 0)
    if action in {"render", "reduce_information", None}:
        return "safe_area_gate"
    if action == "regenerate_background" and attempts <= 1:
        return "image_prompt_planner"
    if action in {"rewrite_copy", "manual_review"}:
        return "result"
    return "result"


def route_after_t2i_generation(state: MarketingState) -> str:
    status = state.get("status")
    if status in {"modal_running", "failed"}:
        return END
    return "background_ocr_gate"


def route_after_ocr_gate(state: MarketingState) -> str:
    decision = state.get("ocr_gate_decision")
    attempts = int(state.get("ocr_revision_attempts") or 0)
    if not ocr_settings.is_ocr_gate_enabled():
        return "continue"
    if decision == "reject":
        return "rejected_result"
    if decision in {"manual_review", "unavailable"}:
        return "manual_review_result"
    if not ocr_settings.is_revision_loop_enabled():
        return "continue"
    if decision in {"retry_image", "retry_layout"} and attempts >= ocr_settings.get_max_revisions():
        return "manual_review_result"
    if decision == "retry_image":
        return "ocr_image_revision"
    if decision == "retry_layout":
        return "ocr_layout_revision"
    return "continue"


route_after_validator = route_after_validator_for_intake
