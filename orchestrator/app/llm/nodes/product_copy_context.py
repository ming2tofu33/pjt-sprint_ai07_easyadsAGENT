"""LangGraph node wrapper for product copy context planning."""

from __future__ import annotations

from typing import Any

from orchestrator.app.llm.product_copy_context_service import build_dynamic_product_copy_context


def product_copy_context_node(state: dict[str, Any]) -> dict[str, Any]:
    evidence = state.get("input_evidence_bundle") or {}
    understanding = state.get("product_understanding") or {}
    context = state.get("context") or {}
    copy_context = build_dynamic_product_copy_context(context, understanding, evidence)
    return {
        "product_copy_context": copy_context.model_dump(),
        "copy_presence_plan": copy_context.copy_presence_plan.model_dump(),
        "language_policy": copy_context.language_policy.model_dump(),
        "interaction_copy_plan": copy_context.interaction_plan.model_dump(),
        "product_copy_context_status": "completed",
    }
