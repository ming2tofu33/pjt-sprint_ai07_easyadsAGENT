"""No-copy branch for image-only advertising backgrounds."""

from __future__ import annotations

from typing import Any

from orchestrator.app.graph.state import MarketingState


def no_copy_bypass_node(state: MarketingState) -> dict[str, Any]:
    return {
        "marketing_copy": None,
        "copy_generation_mode": "no_copy",
        "copy_required": False,
        "text_overlay_pending": False,
        "current_brief": {
            **state.get("current_brief", {}),
            "copy_generation_mode": "no_copy",
            "render_text_in_image": False,
        },
        "status": "bypassing_copy",
    }
