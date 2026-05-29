"""LangGraph node for resolving selected reference templates."""

from __future__ import annotations

from typing import Any

from orchestrator.app.graph.state import MarketingState, now_iso
from orchestrator.app.reference_catalog.service import resolve_reference_template_selection


def reference_template_resolve_node(state: MarketingState) -> dict[str, Any]:
    template_id = state.get("selected_reference_template_id")
    if not template_id:
        return {}

    selection = resolve_reference_template_selection(str(template_id))
    template = selection.resolved_template
    current_brief = dict(state.get("current_brief") or {})
    artifact_refs = list(state.get("artifact_refs") or [])
    updates: dict[str, Any] = {
        "reference_template_selection": selection.model_dump(mode="json"),
        "updated_at": now_iso(),
        "current_brief": current_brief,
        "artifact_refs": artifact_refs,
    }

    if not template:
        current_brief["reference_template_error"] = "reference_template_not_found"
        updates["error_message"] = f"reference_template_not_found: {template_id}"
        return updates

    template_dump = template.model_dump(mode="json")
    current_brief["reference_template_selected"] = True
    current_brief["selected_reference_template_id"] = template.template_id
    current_brief["reference_template_style_hint"] = selection.style_profile_hint
    updates["selected_reference_template"] = template_dump
    if selection.reference_image_path:
        updates["reference_image_path"] = selection.reference_image_path
    else:
        current_brief["reference_template_warning"] = "source_image_path_missing"

    artifact_refs.append(
        {
            "artifact_id": f"ref_template_{template.template_id}",
            "artifact_type": "reference_template",
            "path": template.assets.preview_path or template.assets.thumbnail_path or "",
            "label": template.title,
            "metadata": template_dump,
        }
    )
    return updates
