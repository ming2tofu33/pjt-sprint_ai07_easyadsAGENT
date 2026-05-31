"""Shared marketing graph instance for API adapters."""

from __future__ import annotations

from orchestrator.app.graph.builder import build_marketing_graph


MARKETING_GRAPH = build_marketing_graph()
