"""LangGraph helpers for EasyAds LLM workflows."""

from orchestrator.app.graph.state import MarketingState, create_initial_marketing_state


def build_intake_graph(*args, **kwargs):
    from orchestrator.app.graph.builder import build_intake_graph as _build_intake_graph

    return _build_intake_graph(*args, **kwargs)


def build_marketing_graph(*args, **kwargs):
    from orchestrator.app.graph.builder import build_marketing_graph as _build_marketing_graph

    return _build_marketing_graph(*args, **kwargs)


__all__ = ["MarketingState", "build_intake_graph", "build_marketing_graph", "create_initial_marketing_state"]
