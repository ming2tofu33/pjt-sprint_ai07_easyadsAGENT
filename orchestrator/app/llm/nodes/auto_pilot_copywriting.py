"""Auto-pilot copywriting branch."""

from __future__ import annotations

from typing import Any

from orchestrator.app.graph.state import MarketingState
from orchestrator.app.llm.nodes.copywriting import copywriting_node


def auto_pilot_copywriting_node(state: MarketingState) -> dict[str, Any]:
    update = copywriting_node(state)
    update["copy_required"] = True
    update["text_overlay_pending"] = True
    update["copy_generation_mode"] = "auto_pilot"
    update["current_brief"] = {
        **state.get("current_brief", {}),
        **update.get("current_brief", {}),
        "copy_generation_mode": "auto_pilot",
    }
    return update
