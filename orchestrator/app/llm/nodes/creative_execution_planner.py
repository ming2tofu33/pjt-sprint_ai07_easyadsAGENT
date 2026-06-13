"""Creative execution planner for native typography vs local lanes."""

from __future__ import annotations

from typing import Any

from orchestrator.app.llm.native_copy_policy import plan_gpt_image2_native_single_shot


def creative_execution_planner_node(state: dict[str, Any]) -> dict[str, Any]:
    engine = str(state.get("engine") or state.get("preferred_engine") or "").lower()
    if engine in {"gpt_image_2", "gpt-image-2"} or state.get("gpt_image2_native_single_shot"):
        plan = plan_gpt_image2_native_single_shot()
        return {
            "creative_execution_plan": plan.model_dump(),
            "native_typography_eligibility": {
                "eligible": True,
                "recommended_lane": "gpt_native_single_shot",
                "reason_codes": ["gpt_image2_native_requested"],
                "blocking_reasons": [],
                "max_text_blocks": 2,
                "max_total_characters": 48,
                "confidence": 0.8,
            },
            "native_generation_status": "planned",
        }
    return {
        "creative_execution_plan": {
            "schema_version": "creative_execution_plan_v1",
            "image_engine": state.get("engine") or "flux2_klein_4b",
            "execution_lane": "local_visual_first",
            "copy_authoring_mode": "gpt_structured",
            "text_rendering_mode": "external_renderer",
            "copy_precision": "semantic",
            "max_text_blocks": 2,
            "native_text_allowed": False,
            "image_call_limit": 1,
            "automatic_edit_allowed": False,
            "automatic_retry_allowed": False,
            "external_renderer_fallback_allowed": False,
            "reason_codes": ["local_lane_default"],
        }
    }
