"""Tracking-aware graph factory.

Injects per-node DB wrappers at StateGraph.add_node() time via a temporary
monkeypatch so builder.py edge structure is reused verbatim — no changes to
builder.py, state.py, or nodes.py required.
"""

from __future__ import annotations

from typing import Any, Callable

from orchestrator.app.graph.builder import build_intake_graph as _build_intake
from orchestrator.app.graph.builder import build_marketing_graph as _build_marketing
from orchestrator.eval.ops_db import OpsDBWriter
from orchestrator.eval.tracking import make_tracking_wrapper


def _build_with_tracking(
    build_fn: Callable,
    graph_name: str,
    checkpointer: Any,
    db_writer: OpsDBWriter,
) -> Any:
    from langgraph.graph import StateGraph

    _original = StateGraph.add_node  # type: ignore[attr-defined]

    def _patched(self_sg: Any, node: str, action: Callable | None = None, **kwargs: Any) -> Any:
        if callable(action) and db_writer is not None:
            action = make_tracking_wrapper(action, node, graph_name, db_writer)
        return _original(self_sg, node, action, **kwargs)

    StateGraph.add_node = _patched  # type: ignore[method-assign]
    try:
        return build_fn(checkpointer=checkpointer)
    finally:
        StateGraph.add_node = _original  # type: ignore[method-assign]


def build_tracked_marketing_graph(
    checkpointer: Any = None,
    db_writer: OpsDBWriter | None = None,
) -> Any:
    if db_writer is None:
        from orchestrator.eval.config import OPS_DB_PATH
        db_writer = OpsDBWriter(OPS_DB_PATH)
    return _build_with_tracking(_build_marketing, "marketing", checkpointer, db_writer)


def build_tracked_intake_graph(
    checkpointer: Any = None,
    db_writer: OpsDBWriter | None = None,
) -> Any:
    if db_writer is None:
        from orchestrator.eval.config import OPS_DB_PATH
        db_writer = OpsDBWriter(OPS_DB_PATH)
    return _build_with_tracking(_build_intake, "intake", checkpointer, db_writer)
