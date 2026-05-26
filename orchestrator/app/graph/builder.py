"""Builder for the LLM/LangGraph intake mini graph."""

from __future__ import annotations

from langgraph.graph import END, StateGraph

try:
    from langgraph.checkpoint.memory import InMemorySaver
except ImportError:  # pragma: no cover - older langgraph fallback
    from langgraph.checkpoint.memory import MemorySaver as InMemorySaver

from orchestrator.app.graph.nodes import input_node, options_node, state_update_node, validator_node
from orchestrator.app.graph.routers import route_after_validator
from orchestrator.app.graph.state import MarketingState


def build_intake_graph(checkpointer=None):
    graph = StateGraph(MarketingState)
    graph.add_node("input", input_node)
    graph.add_node("validator", validator_node)
    graph.add_node("options", options_node)
    graph.add_node("state_update", state_update_node)

    graph.set_entry_point("input")
    graph.add_edge("input", "validator")
    graph.add_conditional_edges("validator", route_after_validator, {"options": "options", END: END})
    graph.add_edge("options", "state_update")
    graph.add_edge("state_update", "validator")

    return graph.compile(checkpointer=checkpointer or InMemorySaver())
