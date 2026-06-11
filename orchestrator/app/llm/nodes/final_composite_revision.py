"""Final composite revision planner."""

from __future__ import annotations

from typing import Any

from orchestrator.app.graph.state import MarketingState
from orchestrator.app.quality_gate.final_composite_schemas import CompositeRevisionPlan


TOTAL_BUDGET = 5
ACTION_BUDGET_KEYS = {
    "rewrite_copy": "final_copy_revision_attempts",
    "shorten_copy": "final_copy_revision_attempts",
    "retry_layout": "final_layout_revision_attempts",
    "retry_text_style": "final_style_revision_attempts",
    "reduce_cta_emphasis": "final_style_revision_attempts",
    "regenerate_background": "final_background_regeneration_attempts",
}
ACTION_LIMITS = {
    "final_copy_revision_attempts": 1,
    "final_layout_revision_attempts": 2,
    "final_style_revision_attempts": 2,
    "final_background_regeneration_attempts": 1,
}
RERUN_NODE = {
    "rewrite_copy": "final_copy_revision",
    "shorten_copy": "final_copy_revision",
    "retry_layout": "post_t2i_layout_refiner",
    "retry_text_style": "adaptive_typography_refiner",
    "reduce_cta_emphasis": "adaptive_typography_refiner",
    "regenerate_background": "image_prompt_planner",
}
DIRTY_FIELDS = {
    "rewrite_copy": ["marketing_copy", "copy_spec", "render_result", "final_validation_report"],
    "shorten_copy": ["copy_spec", "render_result", "final_validation_report"],
    "retry_layout": ["text_layout_spec", "render_result", "final_validation_report"],
    "retry_text_style": ["text_style_spec", "render_result", "final_validation_report"],
    "reduce_cta_emphasis": ["text_style_spec", "render_result", "final_validation_report"],
    "regenerate_background": ["image_prompt_spec", "t2i_request", "t2i_result", "render_result", "final_validation_report"],
}
PRESERVED_BY_ACTION = {
    "rewrite_copy": ["job_id", "thread_id", "workspace_id", "t2i_result", "background_image_path", "image_layout_analysis", "source_asset_id", "reference_asset_id", "artifact_refs"],
    "shorten_copy": ["job_id", "thread_id", "workspace_id", "t2i_result", "background_image_path", "image_layout_analysis", "source_asset_id", "reference_asset_id", "artifact_refs"],
    "retry_layout": ["job_id", "thread_id", "workspace_id", "marketing_copy", "copy_spec", "t2i_result", "background_image_path", "source_asset_id", "reference_asset_id", "artifact_refs"],
    "retry_text_style": ["job_id", "thread_id", "workspace_id", "marketing_copy", "copy_spec", "t2i_result", "background_image_path", "source_asset_id", "reference_asset_id", "artifact_refs"],
    "reduce_cta_emphasis": ["job_id", "thread_id", "workspace_id", "marketing_copy", "copy_spec", "t2i_result", "background_image_path", "source_asset_id", "reference_asset_id", "artifact_refs"],
    "regenerate_background": ["job_id", "thread_id", "workspace_id", "marketing_copy", "copy_spec", "source_asset_id", "reference_asset_id"],
}


def final_composite_revision_node(state: MarketingState) -> dict[str, Any]:
    report = state.get("final_composite_quality_report") or {}
    action = str(report.get("primary_action") or "manual_review")
    attempt = int(state.get("final_composite_attempts") or 0) + 1
    budget_before = _budget_snapshot(state)
    budget_after = dict(budget_before)

    rerun_from_node = RERUN_NODE.get(action)
    status = "final_composite_revising" if rerun_from_node else "manual_review"
    if attempt > TOTAL_BUDGET:
        action = "manual_review"
        rerun_from_node = None
        status = "manual_review"

    budget_key = ACTION_BUDGET_KEYS.get(action)
    if budget_key:
        budget_after[budget_key] = budget_after.get(budget_key, 0) + 1
        if budget_after[budget_key] > ACTION_LIMITS[budget_key]:
            action = "manual_review"
            rerun_from_node = None
            status = "manual_review"

    plan = CompositeRevisionPlan(
        action=action,  # type: ignore[arg-type]
        rerun_from_node=rerun_from_node,
        dirty_fields=DIRTY_FIELDS.get(action, []),
        preserved_fields=PRESERVED_BY_ACTION.get(action, []),
        feedback=list(report.get("retry_feedback") or []),
        budget_before=budget_before,
        budget_after=budget_after,
    )
    updates: dict[str, Any] = {
        "final_composite_attempts": attempt,
        "final_composite_revision_plan": plan.model_dump(),
        "final_composite_retry_feedback": plan.feedback,
        "final_composite_partial_rerun": action != "regenerate_background" and bool(rerun_from_node),
        "final_composite_rerun_action": action,
        "reuse_existing_background": action != "regenerate_background",
        "final_composite_revision_patch": _patch_for_action(action, report),
        "dirty_fields": plan.dirty_fields,
        "status": status,
    }
    if budget_key:
        updates[budget_key] = budget_after[budget_key]
    return updates


def _patch_for_action(action: str, report: dict[str, Any]) -> dict[str, Any]:
    if action == "reduce_cta_emphasis":
        return {"cta_visibility": "optional", "cta_treatment": "text_link", "cta_scale_delta": -0.25, "forbid_full_width_pill": True}
    if action == "retry_text_style":
        return {"contrast_target": "increase", "overlay_treatment": "soft_gradient_veil", "strengthen_headline_body_hierarchy": True, "remove_font_fallback": True}
    if action == "retry_layout":
        return {"exclude_previous_candidate": True, "overlap_feedback": report.get("failure_types") or [], "safe_margin": "increase", "move_text_region": True}
    if action == "regenerate_background":
        return {"reserved_text_area": "strong", "subject_side": "locked", "forbid_fake_text": True, "negative_space": "increase"}
    if action in {"rewrite_copy", "shorten_copy"}:
        return {"failure_types": report.get("failure_types") or [], "role_pixel_budget": report.get("deterministic_metrics") or {}}
    return {}


def _budget_snapshot(state: MarketingState) -> dict[str, int]:
    return {
        "final_composite_attempts": int(state.get("final_composite_attempts") or 0),
        "final_copy_revision_attempts": int(state.get("final_copy_revision_attempts") or 0),
        "final_layout_revision_attempts": int(state.get("final_layout_revision_attempts") or 0),
        "final_style_revision_attempts": int(state.get("final_style_revision_attempts") or 0),
        "final_background_regeneration_attempts": int(state.get("final_background_regeneration_attempts") or 0),
    }
