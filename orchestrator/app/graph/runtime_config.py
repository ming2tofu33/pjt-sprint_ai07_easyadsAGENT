"""Runtime configuration helpers for LangGraph invocation."""

from __future__ import annotations

from typing import Any

from orchestrator.app.core.config import get_graph_recursion_limit


def graph_thread_config(thread_id: str) -> dict[str, Any]:
    return {
        "configurable": {"thread_id": thread_id},
        "recursion_limit": get_graph_recursion_limit(),
    }
