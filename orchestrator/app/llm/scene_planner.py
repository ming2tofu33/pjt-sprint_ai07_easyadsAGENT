from __future__ import annotations

from typing import Any

from orchestrator.app.llm.schemas.image_prompt_v3 import ScenePlan, PromptQualityPolicy
from orchestrator.app.llm.visual_presets import select_visual_preset, VISUAL_PRESETS


def resolve_beauty_subtype(bt_str: str, user_input: str) -> str | None:
    bt_lower = bt_str.lower()
    text = (user_input or "").lower()
    
    is_beauty = any(k in bt_lower for k in ["beauty", "salon", "skincare", "hair", "nail", "spa", "뷰티", "미용", "에스테틱"])
    if not is_beauty:
        return None
        
    # Check text/keywords in user_input
    if any(k in text for k in ["hair", "haircut", "salon", "styling", "헤어", "미용실", "컷", "펌", "염색"]):
        return "beauty_hair"
    elif any(k in text for k in ["skincare", "skin", "facial", "clinic", "피부", "에스테틱", "화장품", "앰플", "크림"]):
        return "beauty_skincare"
    elif any(k in text for k in ["nail", "네일", "젤네일"]):
        return "beauty_nail"
    elif any(k in text for k in ["spa", "massage", "wellness", "스파", "마사지", "웰니스"]):
        return "beauty_spa"
        
    # Check if bt_str itself contains subtype information
    if "hair" in bt_lower:
        return "beauty_hair"
    if "skincare" in bt_lower or "skin" in bt_lower:
        return "beauty_skincare"
    if "nail" in bt_lower:
        return "beauty_nail"
    if "spa" in bt_lower or "massage" in bt_lower:
        return "beauty_spa"
        
    # Ambiguous beauty fallback
    return "beauty_skincare"


def resolve_business_type(
    user_input: str,
    business_type: str | None,
    selected_reference_template: dict[str, Any] | None = None,
    metadata: dict[str, Any] | None = None,
) -> str:
    # 1. explicit metadata.business_type
    if metadata and metadata.get("business_type"):
        bt = metadata.get("business_type")
        resolved = resolve_beauty_subtype(str(bt), user_input)
        if resolved:
            return resolved
        return str(bt)
    
    # 2. selected_reference_template.business_type or category
    if selected_reference_template:
        ref_bt = selected_reference_template.get("business_type") or selected_reference_template.get("category")
        if ref_bt:
            resolved = resolve_beauty_subtype(str(ref_bt), user_input)
            if resolved:
                return resolved
            return str(ref_bt)
            
    # 3. user_input keyword heuristic
    text = (user_input or "").lower()
    if any(k in text for k in ["cafe", "dessert", "bakery", "카페", "디저트", "베이커리"]):
        return "cafe"
    if any(k in text for k in ["bbq", "korean_food", "meat", "고기", "갈비", "삼겹살", "숯불"]):
        return "restaurant_bbq"
    if any(k in text for k in ["restaurant", "식당", "맛집", "치킨", "피자", "food", "음식", "dining"]):
        return "restaurant"
        
    beauty_resolved = resolve_beauty_subtype("beauty", text)
    if beauty_resolved and beauty_resolved != "beauty_skincare":
        return beauty_resolved

    if any(k in text for k in ["beauty", "뷰티", "미용"]):
        return "beauty_skincare"
        
    # 4. fallback
    if business_type:
        resolved = resolve_beauty_subtype(business_type, user_input)
        if resolved:
            return resolved
        return business_type
        
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
