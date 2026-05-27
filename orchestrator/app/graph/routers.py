"""Conditional routers for the LLM/LangGraph intake mini graph."""

from __future__ import annotations

from langgraph.graph import END

from orchestrator.app.graph.state import MarketingState


def route_by_entry_mode(state: MarketingState) -> str:
    return "validator"


def route_after_validator_for_intake(state: MarketingState) -> str:
    if state.get("missing_fields"):
        return "options"
    return END


def route_after_validator_for_marketing(state: MarketingState) -> str:
    if state.get("missing_fields"):
        return "options"
    return "format_planner"


route_after_validator = route_after_validator_for_intake
