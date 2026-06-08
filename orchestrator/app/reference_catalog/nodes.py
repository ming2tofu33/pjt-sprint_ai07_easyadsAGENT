"""LangGraph node for resolving selected reference templates."""

from __future__ import annotations

from typing import Any

from orchestrator.app.graph.state import MarketingState, now_iso
from orchestrator.app.reference_catalog.service import resolve_reference_template_selection
from orchestrator.app.schemas.reference_catalog import ReferenceTemplate


BUSINESS_TYPE_ALIASES = {
    "bbq": "restaurant",
    "beauty": "beauty_salon",
    "cafe": "cafe",
    "coffee": "cafe",
    "dessert": "cafe",
    "fitness": "fitness",
    "flower": "flower_shop",
    "flower_shop": "flower_shop",
    "food": "restaurant",
    "meat": "restaurant",
    "restaurant": "restaurant",
    "retail": "store",
    "salon": "beauty_salon",
    "store": "store",
}


def _canonical_business_type(value: str | None) -> str | None:
    if not value:
        return None
    normalized = value.strip().lower()
    return BUSINESS_TYPE_ALIASES.get(normalized, normalized or None)


def _template_text(template: ReferenceTemplate) -> str:
    return " ".join(
        str(value or "")
        for value in [
            template.title,
            template.description,
            template.category,
            template.sub_category,
            " ".join(template.tags),
            " ".join(template.business_types),
            " ".join(template.style_keywords),
            template.background_style,
        ]
    )


def _template_context_defaults(template: ReferenceTemplate) -> dict[str, Any]:
    from orchestrator.app.graph.nodes import infer_marketing_context

    defaults = infer_marketing_context(_template_text(template))
    if not defaults.get("business_type"):
        for candidate in [*template.business_types, template.category]:
            business_type = _canonical_business_type(candidate)
            if business_type:
                defaults["business_type"] = business_type
                break
    if not defaults.get("ad_format") and template.ad_formats:
        defaults["ad_format"] = template.ad_formats[0]
    return defaults


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
    context = dict(state.get("context") or {})
    extra = dict(context.get("extra") or {})
    context_defaults = _template_context_defaults(template)

    for field in ("business_type", "item_or_service", "promotion_goal"):
        value = context_defaults.get(field)
        if value and not context.get(field):
            context[field] = value

    template_ad_format = context_defaults.get("ad_format")
    if template_ad_format and not extra.get("ad_format"):
        extra["ad_format"] = template_ad_format
    extra["selected_reference_template_id"] = template.template_id
    extra["reference_template_title"] = template.title
    extra["reference_template_category"] = template.category
    extra["reference_template_business_types"] = template.business_types
    extra["reference_template_ad_formats"] = template.ad_formats
    context["extra"] = extra

    current_brief["reference_template_selected"] = True
    current_brief["selected_reference_template_id"] = template.template_id
    current_brief["reference_template_style_hint"] = selection.style_profile_hint
    if template_ad_format and not current_brief.get("requested_ad_format"):
        current_brief["requested_ad_format"] = template_ad_format
    updates["selected_reference_template"] = template_dump
    updates["context"] = context
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
