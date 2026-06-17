"""Builder for the LLM/LangGraph intake mini graph."""

from __future__ import annotations

import inspect
from functools import wraps

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
    route_after_product_understanding,
    route_after_reference_template_resolve,
    route_after_ocr_gate,
    route_after_t2i_generation,
    route_after_layout_refiner,
    route_after_final_composite_revision,
    route_after_final_validation,
    route_after_text_layout_planner,
    route_after_tone_binding,
    route_after_validator_for_intake,
    route_after_validator_for_marketing,
    route_by_copy_presence,
    route_after_compliance_gate,
    route_after_compliance_resolution,
    route_after_native_copy_brief,
    route_after_native_preflight,
)
from orchestrator.app.graph.state import MarketingState
from orchestrator.app.llm.nodes.auto_pilot_copywriting import auto_pilot_copywriting_node
from orchestrator.app.llm.nodes.background_validation import background_validation_node
from orchestrator.app.llm.nodes.copy_candidates import copy_candidate_generation_node, copy_candidate_selection_interrupt_node, state_update_selected_copy_node
from orchestrator.app.llm.nodes.copywriting import copywriting_node
from orchestrator.app.llm.nodes.copy_spec_parser import copy_spec_parser_node
from orchestrator.app.llm.nodes.custom_copy import custom_copy_input_interrupt_node, custom_copy_validation_node
from orchestrator.app.llm.nodes.final_composite_revision import final_composite_revision_node
from orchestrator.app.llm.nodes.final_copy_revision import final_copy_revision_node
from orchestrator.app.llm.nodes.final_validation import final_validation_node
from orchestrator.app.llm.nodes.format_planner import format_planner_node
from orchestrator.app.llm.nodes.adaptive_typography_refiner import adaptive_typography_refiner_node
from orchestrator.app.llm.nodes.image_prompt_planner import image_prompt_planner_node
from orchestrator.app.llm.nodes.image_layout_analyzer import image_layout_analyzer_node
from orchestrator.app.llm.nodes.input_evidence_normalizer import input_evidence_normalizer_node
from orchestrator.app.llm.nodes.product_understanding import product_understanding_node
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
from orchestrator.app.llm.nodes.design_recommendation_node import design_recommendation_node
from orchestrator.app.llm.nodes.html_text_renderer import html_text_renderer_node
from orchestrator.app.llm.nodes.poster_renderer import poster_renderer_node
from orchestrator.app.llm.nodes.poster_layout_planner import poster_layout_planner_node
from orchestrator.app.llm.nodes.image_analysis import image_analysis_node
from orchestrator.app.llm.nodes.image_aware_quality_gate import image_aware_quality_gate_node
from orchestrator.app.llm.nodes.text_layout_planner import text_layout_planner_node
from orchestrator.app.llm.nodes.text_style_binder import text_style_binder_node
from orchestrator.app.llm.nodes.typography_art_director import typography_art_direction_node
from orchestrator.app.llm.nodes.tone_binding import tone_binding_node
from orchestrator.app.reference_catalog.nodes import reference_template_resolve_node
from orchestrator.app.vision.nodes import product_preprocess_node, reference_preprocess_node
from orchestrator.app.observability.performance import estimate_json_size_bytes, perf_span, perf_trace_enabled


# Optional test overrides. Production resolves the real native nodes lazily.
creative_execution_planner_node = None
native_copy_brief_node = None
native_creative_preflight_node = None
gpt_image_2_native_single_shot_node = None
native_generation_review_node = None
native_result_adapter_node = None


def _instrument_node(node_name, fn):
    def build_metadata(state):
        input_size = estimate_json_size_bytes(state)
        return {
            "node_name": node_name,
            "input_key_count": len(state) if isinstance(state, dict) else None,
            "input_state_size_bytes": input_size,
            "size_method": "json_estimate" if input_size is not None else "unavailable",
        }

    def finish_metadata(timer, result):
        output_size = estimate_json_size_bytes(result)
        timer.metadata = {
            **(timer.metadata or {}),
            "output_key_count": len(result) if isinstance(result, dict) else None,
            "output_state_size_bytes": output_size,
        }

    if inspect.iscoroutinefunction(fn):
        @wraps(fn)
        async def async_wrapped(state):
            if not perf_trace_enabled():
                return await fn(state)
            with perf_span("graph_node", operation=node_name, metadata=build_metadata(state)) as timer:
                result = await fn(state)
                finish_metadata(timer, result)
                return result

        return async_wrapped

    @wraps(fn)
    def wrapped(state):
        if not perf_trace_enabled():
            return fn(state)
        with perf_span("graph_node", operation=node_name, metadata=build_metadata(state)) as timer:
            result = fn(state)
            finish_metadata(timer, result)
            return result

    return wrapped


def build_intake_graph(checkpointer=None):
    graph = StateGraph(MarketingState)
    graph.add_node("input", _instrument_node("input", input_node))
    graph.add_node("input_evidence_normalizer", _instrument_node("input_evidence_normalizer", input_evidence_normalizer_node))
    graph.add_node("product_understanding", _instrument_node("product_understanding", product_understanding_node))
    graph.add_node("validator", _instrument_node("validator", validator_node))
    graph.add_node("options", _instrument_node("options", options_node))
    graph.add_node("state_update", _instrument_node("state_update", state_update_node))

    graph.set_entry_point("input")
    graph.add_edge("input", "input_evidence_normalizer")
    graph.add_edge("input_evidence_normalizer", "product_understanding")
    graph.add_conditional_edges("product_understanding", route_after_product_understanding, {"validator": "validator", "result": END})
    graph.add_conditional_edges("validator", route_after_validator_for_intake, {"options": "options", END: END})
    graph.add_edge("options", "state_update")
    graph.add_edge("state_update", "input_evidence_normalizer")

    return graph.compile(checkpointer=checkpointer or InMemorySaver())


def build_marketing_graph(checkpointer=None):
    # Lazy imports avoid graph.state -> graph package -> builder import cycles for
    # native nodes that themselves depend on graph.state.
    from orchestrator.app.llm.nodes.creative_execution_planner import creative_execution_planner_node as default_execution_planner
    from orchestrator.app.llm.nodes.native_copy_brief import native_copy_brief_node as default_copy_brief
    from orchestrator.app.llm.nodes.native_creative_preflight import native_creative_preflight_node as default_preflight
    from orchestrator.app.llm.nodes.native_generation_review import native_generation_review_node as default_review
    from orchestrator.app.llm.nodes.native_result_adapter import native_result_adapter_node as default_result_adapter
    from orchestrator.app.t2i.nodes.gpt_image_2_native_single_shot import gpt_image_2_native_single_shot_node as default_single_shot

    execution_planner = creative_execution_planner_node or default_execution_planner
    copy_brief = native_copy_brief_node or default_copy_brief
    preflight = native_creative_preflight_node or default_preflight
    single_shot = gpt_image_2_native_single_shot_node or default_single_shot
    generation_review = native_generation_review_node or default_review
    result_adapter = native_result_adapter_node or default_result_adapter

    graph = StateGraph(MarketingState)
    graph.add_node("input", _instrument_node("input", input_node))
    graph.add_node("reference_template_resolve", _instrument_node("reference_template_resolve", reference_template_resolve_node))
    graph.add_node("product_preprocess", _instrument_node("product_preprocess", product_preprocess_node))
    graph.add_node("reference_preprocess", _instrument_node("reference_preprocess", reference_preprocess_node))
    graph.add_node("input_evidence_normalizer", _instrument_node("input_evidence_normalizer", input_evidence_normalizer_node))
    graph.add_node("product_understanding", _instrument_node("product_understanding", product_understanding_node))
    graph.add_node("validator", _instrument_node("validator", validator_node))
    graph.add_node("options", _instrument_node("options", options_node))
    graph.add_node("state_update", _instrument_node("state_update", state_update_node))
    graph.add_node("format_planner", _instrument_node("format_planner", format_planner_node))
    graph.add_node("tone_binding", _instrument_node("tone_binding", tone_binding_node))
    graph.add_node("copy_candidate_generation", _instrument_node("copy_candidate_generation", copy_candidate_generation_node))
    graph.add_node("copy_candidate_selection_interrupt", _instrument_node("copy_candidate_selection_interrupt", copy_candidate_selection_interrupt_node))
    graph.add_node("state_update_selected_copy", _instrument_node("state_update_selected_copy", state_update_selected_copy_node))
    graph.add_node("auto_pilot_copywriting", _instrument_node("auto_pilot_copywriting", auto_pilot_copywriting_node))
    graph.add_node("custom_copy_input", _instrument_node("custom_copy_input", custom_copy_input_interrupt_node))
    graph.add_node("custom_copy_validation", _instrument_node("custom_copy_validation", custom_copy_validation_node))
    graph.add_node("input_compliance_precheck", _instrument_node("input_compliance_precheck", input_compliance_precheck_node))
    graph.add_node("no_copy_bypass", _instrument_node("no_copy_bypass", no_copy_bypass_node))
    graph.add_node("copy_compliance_gate", _instrument_node("copy_compliance_gate", copy_compliance_gate_node))
    graph.add_node("copy_compliance_interrupt", _instrument_node("copy_compliance_interrupt", copy_compliance_interrupt_node))
    graph.add_node("copy_compliance_resolution", _instrument_node("copy_compliance_resolution", copy_compliance_resolution_node))
    graph.add_node("copy_spec_parser", _instrument_node("copy_spec_parser", copy_spec_parser_node))
    graph.add_node("typography_art_direction", _instrument_node("typography_art_direction", typography_art_direction_node))
    graph.add_node("text_style_binder", _instrument_node("text_style_binder", text_style_binder_node))
    graph.add_node("text_layout_planner", _instrument_node("text_layout_planner", text_layout_planner_node))
    graph.add_node("image_prompt_planner", _instrument_node("image_prompt_planner", image_prompt_planner_node))
    graph.add_node("prompt_renderer", _instrument_node("prompt_renderer", prompt_renderer_node))
    graph.add_node("t2i_request_builder", _instrument_node("t2i_request_builder", t2i_request_builder_node))
    graph.add_node("t2i_generation", _instrument_node("t2i_generation", t2i_generation_node))
    graph.add_node("background_ocr_gate", _instrument_node("background_ocr_gate", background_ocr_gate_node))
    graph.add_node("ocr_image_revision", _instrument_node("ocr_image_revision", ocr_image_revision_node))
    graph.add_node("background_validation", _instrument_node("background_validation", background_validation_node))
    graph.add_node("image_layout_analyzer", _instrument_node("image_layout_analyzer", image_layout_analyzer_node))
    graph.add_node("post_t2i_layout_refiner", _instrument_node("post_t2i_layout_refiner", post_t2i_layout_refiner_node))
    graph.add_node("adaptive_typography_refiner", _instrument_node("adaptive_typography_refiner", adaptive_typography_refiner_node))
    graph.add_node("safe_area_gate", _instrument_node("safe_area_gate", safe_area_gate_node))
    graph.add_node("text_renderer", _instrument_node("text_renderer", text_renderer_node))
    graph.add_node("html_text_renderer", _instrument_node("html_text_renderer", html_text_renderer_node))
    graph.add_node("image_analysis", _instrument_node("image_analysis", image_analysis_node))
    graph.add_node("poster_layout_planner", _instrument_node("poster_layout_planner", poster_layout_planner_node))
    graph.add_node("poster_renderer", _instrument_node("poster_renderer", poster_renderer_node))
    graph.add_node("image_aware_quality_gate", _instrument_node("image_aware_quality_gate", image_aware_quality_gate_node))
    graph.add_node("design_recommendation", _instrument_node("design_recommendation", design_recommendation_node))
    graph.add_node("final_ocr_gate", _instrument_node("final_ocr_gate", final_ocr_gate_node))
    graph.add_node("ocr_layout_revision", _instrument_node("ocr_layout_revision", ocr_layout_revision_node))
    graph.add_node("readability_gate", _instrument_node("readability_gate", readability_gate_node))
    graph.add_node("final_validation", _instrument_node("final_validation", final_validation_node))
    graph.add_node("final_composite_revision", _instrument_node("final_composite_revision", final_composite_revision_node))
    graph.add_node("final_copy_revision", _instrument_node("final_copy_revision", final_copy_revision_node))
    graph.add_node("result", _instrument_node("result", result_node))
    graph.add_node("creative_execution_planner", _instrument_node("creative_execution_planner", execution_planner))
    graph.add_node("native_copy_brief", _instrument_node("native_copy_brief", copy_brief))
    graph.add_node("native_creative_preflight", _instrument_node("native_creative_preflight", preflight))
    graph.add_node("gpt_image_2_native_single_shot", _instrument_node("gpt_image_2_native_single_shot", single_shot))
    graph.add_node("native_generation_review", _instrument_node("native_generation_review", generation_review))
    graph.add_node("native_result_adapter", _instrument_node("native_result_adapter", result_adapter))

    graph.set_entry_point("input")
    graph.add_conditional_edges(
        "input",
        route_after_input_reference_template,
        {
            "reference_template_resolve": "reference_template_resolve",
            "product_preprocess": "product_preprocess",
            "reference_preprocess": "reference_preprocess",
            "validator": "input_evidence_normalizer",
        },
    )
    graph.add_conditional_edges(
        "reference_template_resolve",
        route_after_reference_template_resolve,
        {"product_preprocess": "product_preprocess", "reference_preprocess": "reference_preprocess", "validator": "input_evidence_normalizer"},
    )
    graph.add_conditional_edges(
        "product_preprocess",
        route_after_product_preprocess,
        {"reference_preprocess": "reference_preprocess", "validator": "input_evidence_normalizer", "result": "result"},
    )
    graph.add_edge("reference_preprocess", "input_evidence_normalizer")
    graph.add_edge("input_evidence_normalizer", "product_understanding")
    graph.add_conditional_edges("product_understanding", route_after_product_understanding, {"validator": "validator", "result": "result"})
    graph.add_conditional_edges(
        "validator",
        route_after_validator_for_marketing,
        {"options": "options", "format_planner": "input_compliance_precheck"},
    )
    graph.add_edge("input_compliance_precheck", "format_planner")
    graph.add_edge("options", "state_update")
    graph.add_edge("state_update", "input_evidence_normalizer")
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
            "creative_execution_planner": "creative_execution_planner",
            "copy_compliance_interrupt": "copy_compliance_interrupt",
        },
    )
    graph.add_edge("copy_compliance_interrupt", "copy_compliance_resolution")
    graph.add_conditional_edges(
        "copy_compliance_resolution",
        route_after_compliance_resolution,
        {
            "copy_spec_parser": "copy_spec_parser",
            "creative_execution_planner": "creative_execution_planner",
            "custom_copy_input": "custom_copy_input",
            END: END,
        },
    )
    graph.add_edge("copy_spec_parser", "typography_art_direction")
    graph.add_edge("typography_art_direction", "text_style_binder")
    graph.add_edge("text_style_binder", "text_layout_planner")
    graph.add_conditional_edges(
        "text_layout_planner",
        route_after_text_layout_planner,
        {"post_t2i_layout_refiner": "post_t2i_layout_refiner", "image_prompt_planner": "image_prompt_planner"},
    )
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
    graph.add_conditional_edges("safe_area_gate", route_by_copy_presence, {"result": "result", "text_renderer": "text_renderer", "html_text_renderer": "html_text_renderer", "image_analysis": "image_analysis", "poster_renderer": "poster_renderer"})
    graph.add_edge("image_analysis", "poster_layout_planner")
    graph.add_edge("poster_layout_planner", "poster_renderer")
    graph.add_edge("poster_renderer", "image_aware_quality_gate")
    graph.add_edge("image_aware_quality_gate", "design_recommendation")
    graph.add_edge("design_recommendation", "readability_gate")
    graph.add_edge("html_text_renderer", "final_ocr_gate")
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
    graph.add_conditional_edges("final_validation", route_after_final_validation, {"final_composite_revision": "final_composite_revision", "result": "result"})
    graph.add_conditional_edges(
        "final_composite_revision",
        route_after_final_composite_revision,
        {
            "final_copy_revision": "final_copy_revision",
            "copy_spec_parser": "copy_spec_parser",
            "post_t2i_layout_refiner": "post_t2i_layout_refiner",
            "adaptive_typography_refiner": "adaptive_typography_refiner",
            "image_prompt_planner": "image_prompt_planner",
            "result": "result",
        },
    )
    graph.add_edge("final_copy_revision", "copy_spec_parser")
    graph.add_edge("creative_execution_planner", "native_copy_brief")
    graph.add_conditional_edges(
        "native_copy_brief",
        route_after_native_copy_brief,
        {
            "native_creative_preflight": "native_creative_preflight",
            "copy_spec_parser": "copy_spec_parser",
            "native_result_adapter": "native_result_adapter",
        },
    )
    graph.add_conditional_edges(
        "native_creative_preflight",
        route_after_native_preflight,
        {"gpt_image_2_native_single_shot": "gpt_image_2_native_single_shot", "native_result_adapter": "native_result_adapter"},
    )
    graph.add_edge("gpt_image_2_native_single_shot", "native_generation_review")
    graph.add_edge("native_generation_review", "native_result_adapter")
    graph.add_edge("native_result_adapter", "result")
    graph.add_edge("result", END)

    return graph.compile(checkpointer=checkpointer or InMemorySaver())
