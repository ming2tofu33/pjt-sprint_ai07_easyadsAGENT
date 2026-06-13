"""Shared marketing graph singleton for API adapters.

Built lazily on first use so importing this module never opens a DB
connection (the Postgres checkpointer connects in postgres mode only).
"""

from __future__ import annotations

from functools import lru_cache

from orchestrator.app.graph.builder import build_marketing_graph
from orchestrator.app.graph.checkpointer import get_checkpointer


@lru_cache(maxsize=1)
def get_marketing_graph():
    return build_marketing_graph(checkpointer=get_checkpointer())
