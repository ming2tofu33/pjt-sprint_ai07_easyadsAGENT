from __future__ import annotations

from typing import Any

from orchestrator.app.llm.schemas.image_prompt_v3 import ScenePlan, PromptQualityPolicy
from orchestrator.app.llm.visual_presets import PRESET_ID_BY_BUSINESS_TYPE, select_visual_preset


def _exact_visual_route_key(value: str | None) -> str | None:
    key = str(value or "").strip().lower()
    if key in PRESET_ID_BY_BUSINESS_TYPE:
        return key
    return None


def resolve_beauty_subtype(bt_str: str, user_input: str) -> str | None:
    return _exact_visual_route_key(bt_str)


def resolve_business_type(
    user_input: str,
    business_type: str | None,
    selected_reference_template: dict[str, Any] | None = None,
    metadata: dict[str, Any] | None = None,
) -> str:
    candidates: list[str | None] = [
        str((metadata or {}).get("business_type")) if (metadata or {}).get("business_type") else None,
        str((selected_reference_template or {}).get("business_type")) if (selected_reference_template or {}).get("business_type") else None,
        str((selected_reference_template or {}).get("category")) if (selected_reference_template or {}).get("category") else None,
        business_type,
    ]
    for candidate in candidates:
        route_key = _exact_visual_route_key(candidate)
        if route_key:
            return route_key

    return "generic"


def build_scene_plan(
    *,
    user_input: str,
    business_type: str | None,
    ad_format: str | None,
    selected_reference_template: dict[str, Any] | None = None,
    reference_template_selection: dict[str, Any] | None = None,
    metadata: dict[str, Any] | None = None,
) -> ScenePlan:
    """Build deterministic ScenePlan based on input context, templates, and presets."""
    resolved_bt = resolve_business_type(
        user_input=user_input,
        business_type=business_type,
        selected_reference_template=selected_reference_template,
        metadata=metadata,
    )
    
    preset = select_visual_preset(
        business_type=resolved_bt,
        ad_format=ad_format,
        selected_reference_template=selected_reference_template
    )
    
    # Ensure ad_format is valid for schema
    ad_fmt = ad_format if ad_format in ["instagram_feed", "instagram_story", "poster", "banner", "generic"] else "generic"
    
    primary_subject = (metadata or {}).get("item_or_service") or business_type or "advertising background"
    if metadata and metadata.get("item_or_service"):
        primary_subject = str(metadata.get("item_or_service"))
    elif selected_reference_template and selected_reference_template.get("title"):
        primary_subject = f"product inspired by {selected_reference_template.get('title')}"
        
    subject_desc = f"{primary_subject}, presented as {preset['primary_subject_template']}"
    
    scene_plan = ScenePlan(
        business_type=preset["business_type"],
        ad_format=ad_fmt,
        product_or_service=primary_subject,
        target_customer=(metadata or {}).get("target_persona"),
        ad_goal=(metadata or {}).get("promotion_goal"),
        desired_mood=preset["desired_mood"],
        realism_level="premium_realistic",
        primary_subject=subject_desc,
        secondary_props=preset["secondary_props"],
        composition_archetype=preset["composition_archetype"],
        reserved_copy_area=preset["reserved_copy_area"],
        expected_overlay_position=preset["reserved_copy_area"],
        background_density="moderate",
        forbidden_visual_elements=preset["forbidden_visual_elements"],
        fake_text_risk_level="medium",
        reference_alignment_priority="medium",
        notes=[f"Selected preset: {preset['preset_id']}"],
    )
    return scene_plan


def build_prompt_quality_policy(preset: dict[str, Any]) -> PromptQualityPolicy:
    """Build PromptQualityPolicy based on preset properties."""
    return PromptQualityPolicy(
        no_text_policy="Absolutely no text, letters, signage, logos, or watermarks are allowed in the image. Clean backgrounds only.",
        safe_area_policy=f"Keep the {preset['reserved_copy_area']} area completely clear, simple, and low contrast for later copy overlay.",
        brand_safety_policy="Avoid tacky elements, low-quality stock style, or misleading visual claims.",
        stock_like_risk_policy="Avoid crowded table setups or generic visual templates; maintain premium commercial advertising quality.",
        tacky_visual_risk_policy="Ensure high-end styling, consistent lighting, and clean edges.",
        business_fit_policy=f"Ensure the visual elements closely fit the {preset['business_type']} industry constraints.",
        fake_text_negative_terms=preset["negative_terms"],
        positive_safe_area_terms=preset["positive_safe_area_terms"],
        composition_constraints=[f"Place primary subject on the opposite side of the reserved copy area ({preset['reserved_copy_area']})."]
    )
