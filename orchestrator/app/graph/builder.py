"""Builder for the LLM/LangGraph intake mini graph."""

from __future__ import annotations

from langgraph.graph import END, StateGraph

try:
    from langgraph.checkpoint.memory import InMemorySaver
except ImportError:  # pragma: no cover - older langgraph fallback
    from langgraph.checkpoint.memory import MemorySaver as InMemorySaver

from orchestrator.app.graph.nodes import input_node, options_node, state_update_node, validator_node
from orchestrator.app.graph.routers import route_after_validator_for_intake, route_after_validator_for_marketing
from orchestrator.app.graph.state import MarketingState
from orchestrator.app.llm.nodes.copywriting import copywriting_node
from orchestrator.app.llm.nodes.format_planner import format_planner_node
from orchestrator.app.llm.nodes.prompt_optimization import prompt_optimization_node
from orchestrator.app.llm.nodes.prompt_renderer import prompt_renderer_node
from orchestrator.app.llm.nodes.t2i_generation import t2i_generation_node
from orchestrator.app.llm.nodes.t2i_request_builder import t2i_request_builder_node


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
    graph.add_node("validator", validator_node)
    graph.add_node("options", options_node)
    graph.add_node("state_update", state_update_node)
    graph.add_node("format_planner", format_planner_node)
    graph.add_node("copywriting", copywriting_node)
    graph.add_node("prompt_optimization", prompt_optimization_node)
    graph.add_node("prompt_renderer", prompt_renderer_node)
    graph.add_node("t2i_request_builder", t2i_request_builder_node)
    graph.add_node("t2i_generation", t2i_generation_node)

    graph.set_entry_point("input")
    graph.add_edge("input", "validator")
    graph.add_conditional_edges(
        "validator",
        route_after_validator_for_marketing,
        {"options": "options", "format_planner": "format_planner"},
    )
    graph.add_edge("options", "state_update")
    graph.add_edge("state_update", "validator")
    graph.add_edge("format_planner", "copywriting")
    graph.add_edge("copywriting", "prompt_optimization")
    graph.add_edge("prompt_optimization", "prompt_renderer")
    graph.add_edge("prompt_renderer", "t2i_request_builder")
    graph.add_edge("t2i_request_builder", "t2i_generation")
    graph.add_edge("t2i_generation", END)

    return graph.compile(checkpointer=checkpointer or InMemorySaver())
