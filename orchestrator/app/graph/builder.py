"""Builder for the LLM/LangGraph intake mini graph."""

from __future__ import annotations

from langgraph.graph import END, StateGraph

try:
    from langgraph.checkpoint.memory import InMemorySaver
except ImportError:  # pragma: no cover - older langgraph fallback
    from langgraph.checkpoint.memory import MemorySaver as InMemorySaver

from orchestrator.app.graph.nodes import input_node, options_node, state_update_node, validator_node
from orchestrator.app.graph.routers import (
    route_after_input_assets,
    route_after_input_reference_template,
    route_after_product_preprocess,
    route_after_reference_template_resolve,
    route_after_ocr_gate,
    route_after_t2i_generation,
    route_after_layout_refiner,
    route_after_tone_binding,
    route_after_validator_for_intake,
    route_after_validator_for_marketing,
    route_by_copy_presence,
    route_after_compliance_gate,
    route_after_compliance_resolution,
)
from orchestrator.app.graph.state import MarketingState
from orchestrator.app.llm.nodes.auto_pilot_copywriting import auto_pilot_copywriting_node
from orchestrator.app.llm.nodes.background_validation import background_validation_node
from orchestrator.app.llm.nodes.copy_candidates import copy_candidate_generation_node, copy_candidate_selection_interrupt_node, state_update_selected_copy_node
from orchestrator.app.llm.nodes.copywriting import copywriting_node
from orchestrator.app.llm.nodes.copy_spec_parser import copy_spec_parser_node
from orchestrator.app.llm.nodes.custom_copy import custom_copy_input_interrupt_node, custom_copy_validation_node
from orchestrator.app.llm.nodes.final_validation import final_validation_node
from orchestrator.app.llm.nodes.format_planner import format_planner_node
from orchestrator.app.llm.nodes.adaptive_typography_refiner import adaptive_typography_refiner_node
from orchestrator.app.llm.nodes.image_prompt_planner import image_prompt_planner_node
from orchestrator.app.llm.nodes.image_layout_analyzer import image_layout_analyzer_node
from orchestrator.app.llm.nodes.copy_compliance import (
    copy_compliance_gate_node,
    copy_compliance_interrupt_node,
    copy_compliance_resolution_node,
    input_compliance_precheck_node,
)
from orchestrator.app.llm.nodes.no_copy import no_copy_bypass_node
from orchestrator.app.llm.nodes.ocr_gate import background_ocr_gate_node, final_ocr_gate_node, ocr_image_revision_node, ocr_layout_revision_node
from orchestrator.app.llm.nodes.prompt_renderer import prompt_renderer_node
from orchestrator.app.llm.nodes.post_t2i_layout_refiner import post_t2i_layout_refiner_node
from orchestrator.app.llm.nodes.readability_gate import readability_gate_node
from orchestrator.app.llm.nodes.result import result_node
from orchestrator.app.llm.nodes.safe_area_gate import safe_area_gate_node
from orchestrator.app.llm.nodes.t2i_generation import t2i_generation_node
from orchestrator.app.llm.nodes.t2i_request_builder import t2i_request_builder_node
from orchestrator.app.llm.nodes.text_renderer import text_renderer_node
from orchestrator.app.llm.nodes.text_layout_planner import text_layout_planner_node
from orchestrator.app.llm.nodes.text_style_binder import text_style_binder_node
from orchestrator.app.llm.nodes.typography_art_director import typography_art_direction_node
from orchestrator.app.llm.nodes.tone_binding import tone_binding_node
from orchestrator.app.reference_catalog.nodes import reference_template_resolve_node
from orchestrator.app.vision.nodes import product_preprocess_node, reference_preprocess_node


def build_intake_graph(checkpointer=None):
    graph = StateGraph(MarketingState)
    graph.add_node("input", input_node)
    graph.add_node("validator", validator_node)
    graph.add_node("options", options_node)
    graph.add_node("state_update", state_update_node)

    graph.set_entry_point("input")
    graph.add_edge("input", "validator")
    graph.add_conditional_edges("validator", route_after_validator_for_intake, {"options": "options", END: END})
    graph.add_edge("options", "state_update")
    graph.add_edge("state_update", "validator")

    return graph.compile(checkpointer=checkpointer or InMemorySaver())


def build_marketing_graph(checkpointer=None):
    graph = StateGraph(MarketingState)
    graph.add_node("input", input_node)
    graph.add_node("reference_template_resolve", reference_template_resolve_node)
    graph.add_node("product_preprocess", product_preprocess_node)
    graph.add_node("reference_preprocess", reference_preprocess_node)
    graph.add_node("validator", validator_node)
    graph.add_node("options", options_node)
    graph.add_node("state_update", state_update_node)
    graph.add_node("format_planner", format_planner_node)
    graph.add_node("tone_binding", tone_binding_node)
    graph.add_node("copy_candidate_generation", copy_candidate_generation_node)
    graph.add_node("copy_candidate_selection_interrupt", copy_candidate_selection_interrupt_node)
    graph.add_node("state_update_selected_copy", state_update_selected_copy_node)
    graph.add_node("auto_pilot_copywriting", auto_pilot_copywriting_node)
    graph.add_node("custom_copy_input", custom_copy_input_interrupt_node)
    graph.add_node("custom_copy_validation", custom_copy_validation_node)
    graph.add_node("input_compliance_precheck", input_compliance_precheck_node)
    graph.add_node("no_copy_bypass", no_copy_bypass_node)
    graph.add_node("copy_compliance_gate", copy_compliance_gate_node)
    graph.add_node("copy_compliance_interrupt", copy_compliance_interrupt_node)
    graph.add_node("copy_compliance_resolution", copy_compliance_resolution_node)
    graph.add_node("copy_spec_parser", copy_spec_parser_node)
    graph.add_node("typography_art_direction", typography_art_direction_node)
    graph.add_node("text_style_binder", text_style_binder_node)
    graph.add_node("text_layout_planner", text_layout_planner_node)
    graph.add_node("image_prompt_planner", image_prompt_planner_node)
    graph.add_node("prompt_renderer", prompt_renderer_node)
    graph.add_node("t2i_request_builder", t2i_request_builder_node)
    graph.add_node("t2i_generation", t2i_generation_node)
    graph.add_node("background_ocr_gate", background_ocr_gate_node)
    graph.add_node("ocr_image_revision", ocr_image_revision_node)
    graph.add_node("background_validation", background_validation_node)
    graph.add_node("image_layout_analyzer", image_layout_analyzer_node)
    graph.add_node("post_t2i_layout_refiner", post_t2i_layout_refiner_node)
    graph.add_node("adaptive_typography_refiner", adaptive_typography_refiner_node)
    graph.add_node("safe_area_gate", safe_area_gate_node)
    graph.add_node("text_renderer", text_renderer_node)
    graph.add_node("final_ocr_gate", final_ocr_gate_node)
    graph.add_node("ocr_layout_revision", ocr_layout_revision_node)
    graph.add_node("readability_gate", readability_gate_node)
    graph.add_node("final_validation", final_validation_node)
    graph.add_node("result", result_node)

    graph.set_entry_point("input")
    graph.add_conditional_edges(
        "input",
        route_after_input_reference_template,
        {
            "reference_template_resolve": "reference_template_resolve",
            "product_preprocess": "product_preprocess",
            "reference_preprocess": "reference_preprocess",
            "validator": "validator",
        },
    )
    graph.add_conditional_edges(
        "reference_template_resolve",
        route_after_reference_template_resolve,
        {"product_preprocess": "product_preprocess", "reference_preprocess": "reference_preprocess", "validator": "validator"},
    )
    graph.add_conditional_edges(
        "product_preprocess",
        route_after_product_preprocess,
        {"reference_preprocess": "reference_preprocess", "validator": "validator"},
    )
    graph.add_edge("reference_preprocess", "validator")
    graph.add_conditional_edges(
        "validator",
        route_after_validator_for_marketing,
        {"options": "options", "format_planner": "input_compliance_precheck"},
    )
    graph.add_edge("input_compliance_precheck", "format_planner")
    graph.add_edge("options", "state_update")
    graph.add_edge("state_update", "validator")
    graph.add_edge("format_planner", "tone_binding")
    graph.add_conditional_edges(
        "tone_binding",
        route_after_tone_binding,
        {
            "copy_candidate_generation": "copy_candidate_generation",
            "state_update_selected_copy": "state_update_selected_copy",
            "auto_pilot_copywriting": "auto_pilot_copywriting",
            "custom_copy_input": "custom_copy_input",
            "no_copy_bypass": "no_copy_bypass",
        },
    )
    graph.add_edge("copy_candidate_generation", "copy_candidate_selection_interrupt")
    graph.add_edge("copy_candidate_selection_interrupt", "state_update_selected_copy")
    graph.add_edge("state_update_selected_copy", "copy_compliance_gate")
    graph.add_edge("auto_pilot_copywriting", "copy_compliance_gate")
    graph.add_edge("custom_copy_input", "custom_copy_validation")
    graph.add_edge("custom_copy_validation", "copy_compliance_gate")
    graph.add_edge("no_copy_bypass", "copy_spec_parser")
    graph.add_conditional_edges(
        "copy_compliance_gate",
        route_after_compliance_gate,
        {
            "copy_spec_parser": "copy_spec_parser",
            "copy_compliance_interrupt": "copy_compliance_interrupt",
        },
    )
    graph.add_edge("copy_compliance_interrupt", "copy_compliance_resolution")
    graph.add_conditional_edges(
        "copy_compliance_resolution",
        route_after_compliance_resolution,
        {
            "copy_spec_parser": "copy_spec_parser",
            "custom_copy_input": "custom_copy_input",
            END: END,
        },
    )
    graph.add_edge("copy_spec_parser", "typography_art_direction")
    graph.add_edge("typography_art_direction", "text_style_binder")
    graph.add_edge("text_style_binder", "text_layout_planner")
    graph.add_edge("text_layout_planner", "image_prompt_planner")
    graph.add_edge("image_prompt_planner", "prompt_renderer")
    graph.add_edge("prompt_renderer", "t2i_request_builder")
    graph.add_edge("t2i_request_builder", "t2i_generation")
    graph.add_conditional_edges(
        "t2i_generation",
        route_after_t2i_generation,
        {"background_ocr_gate": "background_ocr_gate", END: END},
    )
    graph.add_conditional_edges(
        "background_ocr_gate",
        route_after_ocr_gate,
        {
            "continue": "background_validation",
            "ocr_image_revision": "ocr_image_revision",
            "ocr_layout_revision": "ocr_layout_revision",
            "manual_review_result": "result",
            "rejected_result": "result",
        },
    )
    graph.add_edge("ocr_image_revision", "t2i_generation")
    graph.add_edge("background_validation", "image_layout_analyzer")
    graph.add_edge("image_layout_analyzer", "post_t2i_layout_refiner")
    graph.add_conditional_edges(
        "post_t2i_layout_refiner",
        route_after_layout_refiner,
        {"safe_area_gate": "adaptive_typography_refiner", "image_prompt_planner": "image_prompt_planner", "result": "result"},
    )
    graph.add_edge("adaptive_typography_refiner", "safe_area_gate")
    graph.add_conditional_edges("safe_area_gate", route_by_copy_presence, {"result": "result", "text_renderer": "text_renderer"})
    graph.add_edge("text_renderer", "final_ocr_gate")
    graph.add_conditional_edges(
        "final_ocr_gate",
        route_after_ocr_gate,
        {
            "continue": "readability_gate",
            "ocr_image_revision": "ocr_image_revision",
            "ocr_layout_revision": "ocr_layout_revision",
            "manual_review_result": "result",
            "rejected_result": "result",
        },
    )
    graph.add_edge("ocr_layout_revision", "text_renderer")
    graph.add_edge("readability_gate", "final_validation")
    graph.add_edge("final_validation", "result")
    graph.add_edge("result", END)

    return graph.compile(checkpointer=checkpointer or InMemorySaver())
